"""Synthetic SDK fixtures: no measured simulator or product permit claims."""
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/simulation"))
from pre_execution_support import (SynchronousDispatchLedger, RestProfile,
    measure_rest, refresh_rest, validate_macro_ik, build_preflight, MaterialPatchGeometry)


class TraceFixture:
    def __init__(self, output, velocity=0.):
        self.output=Path(output)
        self.trial_id="fixture-trial"
        self.actions=[]
        self.pending_feedback=[]
        self.step=0
        self.velocity=velocity
        self.names={"left":["a","b"],"right":["c","d"]}
        self.arms={side:SimpleNamespace(get_joint_positions=lambda:np.array([0.,0.]),
                    get_joint_velocities=lambda:np.array([self.velocity,0.])) for side in self.names}
    def clock(self):
        return dict(sim_step=self.step,sim_time_s=self.step/60.,wall_monotonic_ns=time.monotonic_ns())
    def observe(self,*args,**kwargs):
        if self.step:
            self.pending_feedback=[]
        return {"observation_id":"obs"+str(self.step),"rendering_frame":self.step,
                "rendering_time_s":self.step/60.}
    def advance(self):
        self.step+=1


def proposal():
    return dict(trial_id="fixture-trial",candidate_id="candidate",arm="left",
        retreat_world_m=[-.4,.6,.35],pick_world_m=[-.4,.6,.02],lift_world_m=[-.4,.6,.3],
        orientation_wxyz=[1.,0.,0.,0.],open_wait_steps=45,close_wait_steps=12)


def ik_fixture(success=True, q=.1):
    action=SimpleNamespace(joint_positions=np.array([q,q]),joint_indices=np.array([0,1]))
    arm=SimpleNamespace(get_world_pose=lambda:(np.zeros(3),np.array([1.,0.,0.,0.])),
        get_cur_ee_pos=lambda:(np.array([-.4,.6,.3]),np.array([1.,0.,0.,0.])),
        arm_dof_indices=[0,1],dof_properties=[dict(hasLimits=True,lower=-1.,upper=1.)]*2,
        ki_solver=SimpleNamespace(compute_inverse_kinematics=Mock(return_value=(action,success))),
        apply_action=Mock())
    functions=(lambda q,v:np.zeros(3),lambda p,r,b,br:(p,r),
        lambda start_pos,end_pos,num_points:np.linspace(start_pos,end_pos,num_points),
        lambda q:np.eye(3),lambda r:np.array([1.,0.,0.,0.]))
    return arm,functions


class ExecutionSupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trace=TraceFixture(self.tmp.name)
        self.ledger=SynchronousDispatchLedger(self.trace.trial_id,recovery_enabled=True)
        self.ledger.block_normal_dispatch()

    def test_exception_unwinds_measured_counters(self):
        with self.assertRaises(RuntimeError):
            with self.ledger.controller(), self.ledger.dispatch():
                self.assertEqual(self.ledger.active_calls,1)
                raise RuntimeError("anomaly interruption")
        self.assertEqual(self.ledger.active_calls,0)
        self.assertEqual(self.ledger.dispatch_depth,0)
        self.assertEqual(self.ledger.dispatched,0)

    def test_active_controller_refuses_without_advancing(self):
        step=Mock()
        with self.ledger.controller():
            report=measure_rest(self.trace,step,self.ledger)
        self.assertFalse(report["passed"])
        self.assertEqual(report["reason"],"CONTROLLER_NOT_QUIESCENT")
        step.assert_not_called()

    def test_stable_window_requires_actual_physics_samples(self):
        report=measure_rest(self.trace,self.trace.advance,self.ledger)
        self.assertTrue(report["passed"])
        self.assertGreaterEqual(self.trace.step,12)
        self.assertGreaterEqual(len(report["window"]),5)
        self.assertGreaterEqual(report["window"][-1]["end"]["sim_time_s"]-
                                report["window"][0]["end"]["sim_time_s"],.2-1e-9)
        self.assertFalse(report["physical_product_rest_verified"])

    def test_moving_joints_do_not_produce_rest(self):
        self.trace.velocity=.1
        report=measure_rest(self.trace,self.trace.advance,self.ledger,profile=RestProfile(max_steps=15))
        self.assertFalse(report["passed"])
        self.assertEqual(report["reason"],"REST_TIMEOUT")

    def test_nonfinite_velocity_refuses(self):
        self.trace.velocity=float('nan')
        report=measure_rest(self.trace,self.trace.advance,self.ledger)
        self.assertFalse(report["passed"])
        self.assertEqual(report["reason"],"NONFINITE_OR_INVALID_SHAPE")

    def test_new_dispatch_during_rest_refuses(self):
        def bad_step():
            self.trace.advance()
            self.trace.actions.append({"command_id":"unexpected"})
        report=measure_rest(self.trace,bad_step,self.ledger)
        self.assertFalse(report["passed"])
        self.assertEqual(report["reason"],"UNEXPECTED_DISPATCH_DURING_REST")

    def test_rest_refresh_allows_bounded_new_frame_but_rejects_large_gap(self):
        rest=measure_rest(self.trace,self.trace.advance,self.ledger)
        fresh=refresh_rest(self.trace,self.ledger,rest)
        self.assertTrue(fresh["passed"])
        self.trace.advance()
        updated=refresh_rest(self.trace,self.ledger,rest)
        self.assertTrue(updated["passed"])
        self.trace.step+=12
        stale=refresh_rest(self.trace,self.ledger,updated)
        self.assertFalse(stale["passed"])

    def test_rest_refresh_rejects_bad_intermediate_joint_read(self):
        rest=measure_rest(self.trace,self.trace.advance,self.ledger)
        self.trace.advance()
        clock=self.trace.clock()
        self.trace.observations=[dict(joint_read_end=clock,joint_state={
            side:dict(position_rad=[0.,0.],velocity_rad_s=[.2,0.]) for side in self.trace.arms})]
        self.trace.advance()
        self.assertFalse(refresh_rest(self.trace,self.ledger,rest)["passed"])

    def test_repeated_refresh_does_not_inflate_physics_window(self):
        rest=measure_rest(self.trace,self.trace.advance,self.ledger)
        count=len(rest["window"])
        for _ in range(3):
            rest=refresh_rest(self.trace,self.ledger,rest)
            self.assertTrue(rest["passed"])
            self.assertEqual(len(rest["window"]),count)

    def test_rest_refresh_rejects_dispatch_or_generation_change(self):
        for change in ("dispatch","generation"):
            with self.subTest(change=change):
                self.setUp()
                rest=measure_rest(self.trace,self.trace.advance,self.ledger)
                self.trace.advance()
                if change=="dispatch":
                    self.trace.actions.append({"command_id":"unexpected"})
                else:
                    self.ledger.generation+=1
                self.assertFalse(refresh_rest(self.trace,self.ledger,rest)["passed"])

    def test_sampled_ik_checks_all_segments_and_does_not_dispatch(self):
        arm,functions=ik_fixture()
        report=validate_macro_ik(arm,proposal(),self.trace,ik_functions=functions)
        self.assertTrue(report["passed"],report["reason"])
        self.assertEqual({s["operation"] for s in report["samples"]},{"retreat","regrasp","lift"})
        self.assertGreater(len(report["samples"]),50)
        arm.apply_action.assert_not_called()
        self.assertFalse(report["collisions_verified"])

    def test_failed_ik_or_out_of_limit_refuses(self):
        for success,q in ((False,.1),(True,2.)):
            with self.subTest(success=success,q=q):
                arm,functions=ik_fixture(success,q)
                report=validate_macro_ik(arm,proposal(),self.trace,ik_functions=functions)
                self.assertFalse(report["passed"])
                arm.apply_action.assert_not_called()

    def test_bounds_reject_before_ik(self):
        arm,functions=ik_fixture()
        p=proposal();p["pick_world_m"][0]=99.
        report=validate_macro_ik(arm,p,self.trace,ik_functions=functions)
        self.assertFalse(report["passed"])
        arm.ki_solver.compute_inverse_kinematics.assert_not_called()

    def test_bundle_requires_actual_fresh_bound_reports(self):
        arm,functions=ik_fixture()
        p=proposal()
        rest=measure_rest(self.trace,self.trace.advance,self.ledger)
        macro=validate_macro_ik(arm,p,self.trace,ik_functions=functions)
        rest=refresh_rest(self.trace,self.ledger,rest)
        bundle=build_preflight(self.trace,self.ledger,rest,macro,p)
        self.assertTrue(all(bundle[k]["passed"] for k in
                        ("authority","queue_empty","macro_validated","measured_rest")))
        p["pick_world_m"][0]-=.01
        changed=build_preflight(self.trace,self.ledger,rest,macro,p)
        self.assertFalse(changed["macro_validated"]["passed"])
        macro["measured_wall_s"]-=2
        stale=build_preflight(self.trace,self.ledger,rest,macro,proposal())
        self.assertFalse(stale["macro_validated"]["passed"])

    def test_disabled_recovery_and_pending_queue_reject(self):
        self.ledger.recovery_enabled=False
        self.ledger.pending_commands.append("not-run-yet")
        bundle=build_preflight(self.trace,self.ledger,{}, {},proposal())
        self.assertFalse(bundle["authority"]["passed"])
        self.assertFalse(bundle["queue_empty"]["passed"])
        self.assertFalse(bundle["measured_rest"]["passed"])
        self.assertFalse(bundle["macro_validated"]["passed"])
        records=[json.loads(x) for x in (self.trace.output/'execution-measurements.jsonl').read_text().splitlines()]
        self.assertTrue(all(r["trial_id"]==self.trace.trial_id for r in records))

    def test_geometry_uses_fixed_patch_and_physics_clock_not_old_camera_clock(self):
        # Mock only USD access; verify the observation packet consumed by the
        # real geometry monitor distinguishes physics and RGB rendering clocks.
        sampler=MaterialPatchGeometry.__new__(MaterialPatchGeometry)
        sampler.env=object()
        sampler.patch_ids=np.array([0,1])
        sampler.tips=[np.array([0.,0.,.3]),np.array([.02,0.,.3])]
        usd=SimpleNamespace(TimeCode=SimpleNamespace(Default=lambda:None))
        geom=SimpleNamespace(Xformable=lambda tip:SimpleNamespace(
            ComputeLocalToWorldTransform=lambda t:SimpleNamespace(ExtractTranslation=lambda:tip)))
        vertices=np.array([[0.,0.,.3],[.02,0.,.3],[99.,99.,99.]])
        self.trace.step=60
        self.trace.observe=lambda *a,**k:dict(observation_id="fresh-read",rendering_frame=58,rendering_time_s=.95)
        with patch.dict(sys.modules,{"pxr":SimpleNamespace(Usd=usd,UsdGeom=geom)}), \
             patch.object(MaterialPatchGeometry,"vertices",return_value=vertices):
            sample=sampler.capture(self.trace,0)
        self.assertEqual(sample["frame_id"],"physics-step-60")
        self.assertEqual(sample["sim_time_s"],1.)
        self.assertEqual(sample["cloth_xyz_m"],[.01,0.,.3])
        self.assertEqual(sample["provenance"],"privileged_sim_material_patch")

    def test_geometry_rejects_patch_topology_change(self):
        sampler=MaterialPatchGeometry.__new__(MaterialPatchGeometry)
        sampler.env=object();sampler.patch_ids=np.array([2]);sampler.tips=[]
        usd=SimpleNamespace(TimeCode=SimpleNamespace(Default=lambda:None))
        with patch.dict(sys.modules,{"pxr":SimpleNamespace(Usd=usd,UsdGeom=object())}), \
             patch.object(MaterialPatchGeometry,"vertices",return_value=np.zeros((2,3))):
            with self.assertRaisesRegex(ValueError,"PATCH_TOPOLOGY_CHANGED"):
                sampler.capture(self.trace,0)


if __name__ == '__main__':
    unittest.main()
