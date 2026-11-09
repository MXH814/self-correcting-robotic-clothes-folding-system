"""Measured support for the single-threaded, headless simulation diagnostic.

This is not physical-robot authorization, collision checking or product stop
acceptance. Wrap every synchronous dense/hand SDK call in ``ledger.controller``
and every low-level apply_action in ``ledger.dispatch``. On an anomaly, block
normal dispatch, unwind the controller call, then collect rest and nominal-path
IK evidence. No permit is inferred merely from an SDK success return.

Usage (at a controller boundary, with no controller call still on the stack)::

    ledger.block_normal_dispatch()
    rest = measure_rest(trace, physics_step, ledger)
    macro = validate_macro_ik(arm, proposal, trace)
    # IK may take time: refresh by a NEW measurement, never retimestamp a bool.
    rest = refresh_rest(trace, ledger, rest)
    # Acquire/recompute a fresh anomalous RGB report before begin_macro.
    evidence = build_preflight(trace, ledger, rest, macro, proposal)

``physics_step`` must advance physics only, never issue a new controller action.
All reports persist actual values to execution-measurements.jsonl. Bounds and
thresholds below are explicit diagnostic configuration, not validated SRS limits.
The ledger proves only the instrumented synchronous script has no pending work.
"""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import time
import uuid

import numpy as np


def _finite_array(value, shape=None):
    a = np.asarray(value, dtype=float)
    if (shape is not None and a.shape != shape) or not np.isfinite(a).all():
        raise ValueError("NONFINITE_OR_INVALID_SHAPE")
    return a


def _persist(trace, kind, payload):
    event = dict(schema="simulation-execution-measurement/1", kind=kind,
                 evidence_id=str(uuid.uuid4()), trial_id=trace.trial_id,
                 measured_wall_s=time.monotonic(), clock=trace.clock(),
                 scope="instrumented synchronous headless simulation only", **payload)
    path = Path(trace.output) / "execution-measurements.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, allow_nan=False) + "\n")
        stream.flush()
    event["reference"] = path.name + "#evidence_id=" + event["evidence_id"]
    return event


class SynchronousDispatchLedger:
    """Actual nesting counters, not a declaration that a device has stopped.

    The caller owns dispatch gating; use ``normal_dispatch_allowed`` before its
    normal apply_action call. Macro calls are permitted only after begin_macro.
    """
    def __init__(self, trial_id, *, recovery_enabled, generation=0):
        self.trial_id = trial_id
        self.recovery_enabled = recovery_enabled is True
        self.generation = generation
        self.active_calls = 0
        self.dispatch_depth = 0
        self.dispatched = 0
        self.normal_blocked = False
        self.halted = False
        self.pending_commands = []

    @contextmanager
    def controller(self):
        self.active_calls += 1
        try:
            yield
        finally:
            self.active_calls -= 1

    @contextmanager
    def dispatch(self):
        self.dispatch_depth += 1
        try:
            yield
            self.dispatched += 1
        finally:
            self.dispatch_depth -= 1

    def block_normal_dispatch(self):
        self.normal_blocked = True

    @property
    def normal_dispatch_allowed(self):
        return not self.normal_blocked and not self.halted

    def snapshot(self):
        return dict(trial_id=self.trial_id, generation=self.generation,
                    recovery_enabled=self.recovery_enabled, active_calls=self.active_calls,
                    dispatch_depth=self.dispatch_depth, dispatched=self.dispatched,
                    normal_blocked=self.normal_blocked, halted=self.halted,
                    pending_commands=list(self.pending_commands))


@dataclass(frozen=True)
class RestProfile:
    window_sim_s: float = .2
    min_samples: int = 5
    max_velocity_rad_s: float = .05
    max_displacement_rad: float = .005
    max_steps: int = 180


def _joint_sample(trace):
    begin = trace.clock()
    state = {}
    for side, arm in trace.arms.items():
        q = _finite_array(arm.get_joint_positions())
        dq = _finite_array(arm.get_joint_velocities(), q.shape)
        if q.ndim != 1 or q.size == 0 or len(trace.names[side]) != len(q):
            raise ValueError("JOINT_NAME_OR_SHAPE_MISMATCH")
        state[side] = dict(position_rad=q.tolist(), velocity_rad_s=dq.tolist())
    return dict(begin=begin, end=trace.clock(), joints=state)


def _rest_metrics(samples):
    velocity, displacement = 0., 0.
    for side in samples[0]["joints"]:
        q = np.asarray([s["joints"][side]["position_rad"] for s in samples])
        dq = np.asarray([s["joints"][side]["velocity_rad_s"] for s in samples])
        velocity = max(velocity, float(np.max(np.abs(dq))))
        displacement = max(displacement, float(np.max(np.ptp(q, axis=0))))
    return velocity, displacement


def _queue_empty(trace, ledger):
    return (ledger.active_calls == 0 and ledger.dispatch_depth == 0
            and not ledger.pending_commands and not trace.pending_feedback)


def measure_rest(trace, physics_step, ledger, *, profile=None):
    """Advance only physics until a continuous measured rest window or timeout."""
    profile = profile or RestProfile()
    if (profile.window_sim_s <= 0 or profile.min_samples < 2 or profile.max_steps < 1
            or profile.max_velocity_rad_s <= 0 or profile.max_displacement_rad <= 0):
        raise ValueError("INVALID_REST_PROFILE")
    samples, recent, reason, passed = [], [], "REST_TIMEOUT", False
    initial_dispatches = len(trace.actions)
    if not ledger.normal_blocked or ledger.active_calls or ledger.dispatch_depth:
        return _persist(trace, "rest", dict(passed=False, reason="CONTROLLER_NOT_QUIESCENT",
                        profile=asdict(profile), samples=[], ledger=ledger.snapshot()))
    try:
        for step in range(profile.max_steps + 1):
            if step:
                physics_step()
            # Resolves dispatch feedback on a later physics step without new motion.
            trace.observe("PREFLIGHT_REST", force=True)
            sample = _joint_sample(trace)
            samples.append(sample)
            recent.append(sample)
            t = sample["end"]["sim_time_s"]
            while len(recent) > 1 and recent[1]["end"]["sim_time_s"] <= t-profile.window_sim_s:
                recent.pop(0)
            if len(trace.actions) != initial_dispatches:
                reason = "UNEXPECTED_DISPATCH_DURING_REST"
                break
            if ledger.halted or ledger.active_calls or ledger.dispatch_depth:
                reason = "CONTROLLER_CHANGED_DURING_REST"
                break
            duration = t - recent[0]["end"]["sim_time_s"]
            velocity, displacement = _rest_metrics(recent)
            if (duration >= profile.window_sim_s - 1e-9 and len(recent) >= profile.min_samples
                    and velocity <= profile.max_velocity_rad_s
                    and displacement <= profile.max_displacement_rad and _queue_empty(trace, ledger)):
                passed, reason = True, "CONTINUOUS_JOINT_REST_MEASURED"
                break
    except (ValueError, TypeError, AttributeError) as error:
        reason = str(error)
    return _persist(trace, "rest", dict(passed=passed, reason=reason, profile=asdict(profile),
                    samples=samples, window=recent, ledger=ledger.snapshot(),
                    dispatch_count=initial_dispatches, generation=ledger.generation,
                    physical_product_rest_verified=False))


def refresh_rest(trace, ledger, rest, *, max_gap_sim_s=.1):
    """Extend the measured rest window across a bounded physics-only advance.

    The intervening trace joint observations and a fresh current q/dq read are
    consumed. All samples must still satisfy the same rest limits, no dispatch
    may have occurred, and no measured interval may exceed ``max_gap_sim_s``.
    This permits a new camera frame without relabelling an old rest boolean.
    """
    passed, reason = False, "NO_VALID_REST_WINDOW"
    new, window, profile = None, [], rest.get("profile")
    try:
        if not math.isfinite(max_gap_sim_s) or max_gap_sim_s <= 0:
            raise ValueError("INVALID_REST_REFRESH_GAP")
        new = _joint_sample(trace)
        if rest.get("passed") and rest.get("trial_id") == trace.trial_id:
            previous = rest["window"][-1]
            elapsed = new["begin"]["sim_time_s"] - previous["end"]["sim_time_s"]
            if not 0 <= elapsed <= max_gap_sim_s + 1e-9:
                raise ValueError("REST_REFRESH_GAP_EXCEEDED")
            window = list(rest["window"])
            for obs in getattr(trace,"observations",[]):
                clock = obs.get("joint_read_end",{})
                if previous["end"]["sim_step"] < clock.get("sim_step",-1) < new["end"]["sim_step"]:
                    # Validate every intermediate read, not only the endpoints.
                    joints = obs["joint_state"]
                    for side in trace.arms:
                        _finite_array(joints[side]["position_rad"],(len(trace.names[side]),))
                        _finite_array(joints[side]["velocity_rad_s"],(len(trace.names[side]),))
                    if clock["sim_step"] > window[-1]["end"]["sim_step"]:
                        window.append(dict(begin=clock,end=clock,joints=joints))
            if new["end"]["sim_step"] == previous["end"]["sim_step"]:
                # Repeated read of unchanged physics does not inflate sample count.
                window[-1] = new
            else:
                window.append(new)
            velocity, displacement = _rest_metrics(window)
            gaps = [b["end"]["sim_time_s"]-a["end"]["sim_time_s"] for a,b in zip(window,window[1:])]
            passed = (all(0 < gap <= max_gap_sim_s+1e-9 for gap in gaps)
                      and ledger.generation == rest["generation"]
                      and len(trace.actions) == rest["dispatch_count"] and _queue_empty(trace, ledger)
                      and ledger.normal_blocked and not ledger.halted
                      and velocity <= rest["profile"]["max_velocity_rad_s"]
                      and displacement <= rest["profile"]["max_displacement_rad"])
            reason = "CONTINUOUS_REST_WINDOW_EXTENDED_BY_NEW_READ" if passed else "REST_CHANGED_SINCE_WINDOW"
            t = new["end"]["sim_time_s"]
            while len(window)>1 and window[1]["end"]["sim_time_s"] <= t-profile["window_sim_s"]:
                window.pop(0)
            if (len(window) < profile["min_samples"] or
                    window[-1]["end"]["sim_time_s"]-window[0]["end"]["sim_time_s"] < profile["window_sim_s"]-1e-9):
                passed, reason = False, "REST_REFRESH_WINDOW_INSUFFICIENT"
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        reason = str(error)
    return _persist(trace, "rest_refresh", dict(passed=bool(passed), reason=reason,
                    parent_reference=rest.get("reference"), sample=new,
                    window=window,profile=profile,max_gap_sim_s=max_gap_sim_s,
                    generation=ledger.generation, dispatch_count=len(trace.actions),
                    ledger=ledger.snapshot(), physical_product_rest_verified=False))


@dataclass(frozen=True)
class MacroProfile:
    min_xyz_m: tuple = (-.8, .2, -.01)
    max_xyz_m: tuple = (.5, 1.5, .65)
    max_pick_lift_distance_m: float = .32
    dense_sample_scale_m: float = .01
    position_tolerance_m: float = .06


def _upstream_ik_functions():
    from Env_Config.Utils_Project.Transforms import Rotation, get_pose_relat
    from Env_Config.Utils_Project.Code_Tools import dense_trajectory_points_generation
    from isaacsim.core.utils.rotations import quat_to_rot_matrix, rot_matrix_to_quat
    return Rotation, get_pose_relat, dense_trajectory_points_generation, quat_to_rot_matrix, rot_matrix_to_quat


def validate_macro_ik(arm, proposal, trace, *, profile=None, ik_functions=None):
    """No-dispatch nominal path check using the same transforms as upstream dense.

    Future segment starts are nominal targets; subsequent execution must still
    reject SDK failures. This does not check collisions, contact/force limits or
    certify legal physical motion. Passing means only the declared diagnostic
    workspace, sampled IK and returned arm limits passed.
    """
    profile = profile or MacroProfile()
    samples, passed, reason = [], False, "INVALID_MACRO"
    before = len(trace.actions)
    proposal_sha = hashlib.sha256(json.dumps(proposal, sort_keys=True, allow_nan=False).encode()).hexdigest()
    try:
        if proposal.get("trial_id") != trace.trial_id or proposal.get("arm") != "left":
            raise ValueError("MACRO_IDENTITY_OR_ARM_MISMATCH")
        orientation = _finite_array(proposal["orientation_wxyz"], (4,))
        if abs(np.linalg.norm(orientation)-1) > 1e-5:
            raise ValueError("INVALID_QUATERNION")
        targets = [_finite_array(proposal[k], (3,)) for k in
                   ("retreat_world_m", "pick_world_m", "lift_world_m")]
        if any(np.any(p < profile.min_xyz_m) or np.any(p > profile.max_xyz_m) for p in targets):
            raise ValueError("OUTSIDE_DIAGNOSTIC_WORKSPACE")
        if np.linalg.norm(targets[2]-targets[1]) > profile.max_pick_lift_distance_m:
            raise ValueError("PICK_LIFT_EXCEEDS_DIAGNOSTIC_BOUND")
        if proposal.get("open_wait_steps") != 45 or proposal.get("close_wait_steps") != 12:
            raise ValueError("UNEXPECTED_MACRO_WAIT_CONFIGURATION")
        rotation, relative, dense, quat_matrix, matrix_quat = ik_functions or _upstream_ik_functions()
        offset = rotation(orientation, np.array([-.37, -.025, .025]))
        target_rot = quat_matrix(orientation)
        base_pos, base_quat = arm.get_world_pose()
        base_rot = quat_matrix(base_quat)
        current, _ = arm.get_cur_ee_pos()
        current = _finite_array(current, (3,))
        props = arm.dof_properties
        for name, target in zip(("retreat", "regrasp", "lift"), targets):
            wrist = target + offset
            count = int(np.linalg.norm(wrist-current) // profile.dense_sample_scale_m)
            if count < 2:
                raise ValueError("UPSTREAM_DENSE_PATH_TOO_SHORT")
            for xyz in dense(start_pos=current, end_pos=wrist, num_points=count):
                local_pos, local_rot = relative(xyz, target_rot, base_pos, base_rot)
                action, ok = arm.ki_solver.compute_inverse_kinematics(
                    local_pos, matrix_quat(local_rot), position_tolerance=profile.position_tolerance_m)
                if not ok:
                    raise ValueError("NOMINAL_PATH_IK_FAILED:"+name)
                q = _finite_array(action.joint_positions)
                ids = action.joint_indices
                ids = np.asarray(arm.arm_dof_indices if ids is None else ids, dtype=int)
                if q.ndim != 1 or ids.shape != q.shape or len(q) != len(arm.arm_dof_indices):
                    raise ValueError("IK_JOINT_MAPPING_INVALID")
                if set(ids.tolist()) != set(arm.arm_dof_indices):
                    raise ValueError("IK_DID_NOT_RETURN_EXPECTED_ARM_JOINTS")
                for i, value in zip(ids, q):
                    if (i < 0 or i >= len(props) or not props[i]["hasLimits"]
                            or not math.isfinite(float(props[i]["lower"]))
                            or not math.isfinite(float(props[i]["upper"]))
                            or not float(props[i]["lower"]) <= value <= float(props[i]["upper"])):
                        raise ValueError("IK_JOINT_LIMIT_UNCONFIRMED")
                samples.append(dict(operation=name, wrist_world_m=np.asarray(xyz).tolist(),
                                    runtime_indices=ids.tolist(), joint_positions_rad=q.tolist()))
            current = wrist
        if len(trace.actions) != before:
            raise ValueError("UNEXPECTED_DISPATCH_DURING_IK")
        passed, reason = True, "DIAGNOSTIC_NOMINAL_PATH_IK_AND_LIMITS_VERIFIED"
    except (ValueError, TypeError, AttributeError, KeyError, ImportError) as error:
        reason = str(error)
    return _persist(trace, "macro_ik", dict(passed=passed, reason=reason, profile=asdict(profile),
                    candidate_id=proposal.get("candidate_id"), proposal_sha256=proposal_sha,
                    samples=samples, dispatch_count=before,
                    collisions_verified=False, contact_force_limits_verified=False,
                    physical_product_motion_authorized=False))


def build_preflight(trace, ledger, rest, macro, proposal, *, max_age_wall_s=1.):
    """Consume fresh reports and current counters, not caller-supplied booleans."""
    now = time.monotonic()
    def fresh(e):
        t = e.get("measured_wall_s")
        return (e.get("passed") is True and e.get("trial_id") == trace.trial_id
                and isinstance(t, (int, float)) and math.isfinite(t) and 0 <= now-t <= max_age_wall_s
                and isinstance(e.get("reference"), str) and bool(e["reference"]))
    authority = _persist(trace, "authority", dict(passed=bool(ledger.recovery_enabled
            and ledger.trial_id == trace.trial_id and type(ledger.generation) is int
            and ledger.generation >= 0 and ledger.normal_blocked and not ledger.halted),
            ledger=ledger.snapshot(), reason="EXPLICIT_RUN_RECOVERY_SWITCH_AND_CURRENT_LEDGER",
            product_authority_granted=False))
    queue = _persist(trace, "queue", dict(passed=bool(_queue_empty(trace, ledger)
            and ledger.normal_blocked), ledger=ledger.snapshot(),
            pending_feedback_ids=[x.get("command_id") for x in trace.pending_feedback],
            reason="INSTRUMENTED_SYNCHRONOUS_CALLS_UNWOUND_NO_QUEUED_WORK",
            device_queue_verified=False))
    proposal_sha = hashlib.sha256(json.dumps(proposal, sort_keys=True, allow_nan=False).encode()).hexdigest()
    macro_ok = (fresh(macro) and macro.get("kind") == "macro_ik"
                and macro.get("candidate_id") == proposal.get("candidate_id")
                and macro.get("proposal_sha256") == proposal_sha
                and len(trace.actions) == macro.get("dispatch_count"))
    rest_ok = (fresh(rest) and rest.get("kind") in ("rest", "rest_refresh")
               and rest.get("generation") == ledger.generation
               and len(trace.actions) == rest.get("dispatch_count"))
    evidence = dict(trial_id=trace.trial_id, generation=ledger.generation)
    for name, report, ok in (("authority",authority,authority["passed"]),
                              ("queue_empty",queue,queue["passed"]),
                              ("measured_rest",rest,rest_ok), ("macro_validated",macro,macro_ok)):
        evidence[name] = dict(passed=bool(ok), reference=report.get("reference"),
                              measured_wall_s=report.get("measured_wall_s"),
                              reason=report.get("reason"), scope="diagnostic simulation only")
    _persist(trace, "preflight_bundle", dict(evidence=evidence, passed=all(
        evidence[k]["passed"] for k in ("authority","queue_empty","measured_rest","macro_validated"))))
    return evidence


class MaterialPatchGeometry:
    """Read a preselected material patch and two actual fingertip world poses."""
    def __init__(self, env, patch_ids):
        ids = np.asarray(patch_ids)
        if ids.ndim != 1 or len(ids) == 0 or not np.issubdtype(ids.dtype, np.integer) or np.any(ids < 0):
            raise ValueError("INVALID_PATCH_IDS")
        self.env, self.patch_ids = env, ids.copy()
        from pxr import UsdGeom
        self.tips = [env.world.stage.GetPrimAtPath('/World/DexLeft/'+name) for name in ('fftip','thtip')]
        if not all(tip.IsValid() for tip in self.tips):
            raise ValueError("MISSING_ACTUAL_FINGERTIP_PRIM")

    @staticmethod
    def vertices(env):
        from pxr import Usd, UsdGeom
        mesh = env.garment.garment_mesh
        points = _finite_array(mesh._get_points_pose())
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError("INVALID_MATERIAL_VERTICES")
        transform = UsdGeom.Xformable(mesh.prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        return (np.column_stack((points,np.ones(len(points)))) @ np.asarray(transform))[:,:3]

    @classmethod
    def from_pick(cls, env, pick, count=12):
        # Call at initial planned pick, before injecting any fault; never reselect
        # a new nearest patch after loss, which could conceal dropping the cloth.
        points = cls.vertices(env)
        pick = _finite_array(pick, (3,))
        if type(count) is not int or not 1 <= count <= len(points):
            raise ValueError("INVALID_PATCH_SIZE")
        return cls(env, np.argsort(np.linalg.norm(points[:,:2]-pick[:2],axis=1))[:count])

    def capture(self, trace, generation, *, phase="VERIFY_RECOVERY"):
        from pxr import Usd, UsdGeom
        begin = trace.clock()
        points = self.vertices(self.env)
        if np.max(self.patch_ids) >= len(points):
            raise ValueError("PATCH_TOPOLOGY_CHANGED")
        hand = np.asarray([UsdGeom.Xformable(tip).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()).ExtractTranslation() for tip in self.tips]).mean(axis=0)
        cloth = points[self.patch_ids].mean(axis=0)
        _finite_array(hand,(3,)); _finite_array(cloth,(3,))
        obs = trace.observe(phase,force=True)
        end = trace.clock()
        if begin["sim_step"] != end["sim_step"]:
            raise ValueError("GEOMETRY_READ_SPANNED_PHYSICS_STEP")
        sample = dict(trial_id=trace.trial_id,generation=generation,
            observation_id=obs["observation_id"],frame_id='physics-step-'+str(begin["sim_step"]),
            sim_time_s=begin["sim_time_s"],hand_xyz_m=hand.tolist(),cloth_xyz_m=cloth.tolist(),
            provenance="privileged_sim_material_patch",phase=phase,
            captured_wall_s=begin["wall_monotonic_ns"]/1e9,now_wall_s=time.monotonic())
        _persist(trace,"material_patch",dict(passed=True,patch_ids=self.patch_ids.tolist(),
            sample=sample, camera_frame_id=obs["rendering_frame"],
            camera_rendering_time_s=obs["rendering_time_s"],reason="SIMULATION_GEOMETRY_READ"))
        return sample
