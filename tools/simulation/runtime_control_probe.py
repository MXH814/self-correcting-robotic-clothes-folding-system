"""Run a single-process dispatch and stop experiment against live articulations."""
import json
import os
import time
import uuid

import numpy as np
from isaacsim.core.utils.types import ArticulationAction


class ProbeAdapter:
    def __init__(self, robot, log):
        self.arms = (robot.dexleft, robot.dexright)
        self.generation = 0
        self.authorized = True
        self.accepted = {}
        self.log = log

    def dispatch(self, command_id, generation, target, index):
        if generation != self.generation:
            return self.log("rejected_old_generation", command_id=command_id, generation=generation)
        payload = (generation, target, index)
        if command_id in self.accepted:
            status = "deduplicated" if self.accepted[command_id] == payload else "idempotency_conflict"
            return self.log(status, command_id=command_id)
        if not self.authorized:
            return self.log("rejected_no_authority", command_id=command_id)
        self.log("dispatch_intent", command_id=command_id, generation=generation, target_rad=target, index=index)
        self.arms[0].apply_action(ArticulationAction(joint_positions=np.array([target]),
                                                     joint_indices=np.array([index])))
        self.accepted[command_id] = payload
        return self.log("probe_adapter_dispatch_ack", command_id=command_id, generation=generation)

    def revoke_and_hold(self, generation):
        self.authorized = False
        self.generation = generation
        barrier = self.log("probe_adapter_barrier_ack", generation=generation, pending_queue=0)
        for arm in self.arms:
            arm.apply_action(ArticulationAction(joint_positions=arm.get_joint_positions().copy()))
        return barrier


def run_control_probe(world, robot, sample, output):
    events = []
    task = str(uuid.uuid4())
    arms = (robot.dexleft, robot.dexright)

    def log(event, **fields):
        record = dict(event=event, task_id=task, wall_perf_counter_ns=time.perf_counter_ns(),
                      sim_time_s=world.current_time, **fields)
        events.append(record)
        with (output / "control-events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return record

    adapter = ProbeAdapter(robot, log)
    prop = sample["left_dofs"][0]
    all_dofs = sample["left_dofs"] + sample["right_dofs"]
    if any(dof["type"] != "rotation" for dof in all_dofs):
        raise RuntimeError("The stop probe only supports measured revolute joints")

    def new_id():
        return str(uuid.uuid4())

    def motion(offset):
        command = new_id()
        target = float(arms[0].get_joint_positions()[0]) + offset
        if prop["has_limits"] and not prop["lower"] <= target <= prop["upper"]:
            raise RuntimeError("The stop probe target is outside joint limits")
        ack = adapter.dispatch(command, adapter.generation, target, 0)
        assert ack["event"] == "probe_adapter_dispatch_ack"
        duplicate = adapter.dispatch(command, adapter.generation, target, 0)
        assert duplicate["event"] == "deduplicated"
        for _ in range(4):
            world.step(render=False)
        return command, target

    def halt(kind, last_command, old_target):
        request_id = new_id()
        old_generation = adapter.generation
        prior_velocities = np.concatenate([arm.get_joint_velocities() for arm in arms])
        request = log("halt_accepted", request_id=request_id, reason=kind,
                      last_command_id=last_command, generation=old_generation + 1,
                      max_speed_at_request_rad_s=float(np.max(np.abs(prior_velocities))))
        begin = request["wall_perf_counter_ns"]
        adapter.revoke_and_hold(old_generation + 1)
        old = adapter.dispatch(new_id(), old_generation, old_target, 0)
        unauthorized = adapter.dispatch(new_id(), adapter.generation, old_target, 0)
        assert old["event"] == "rejected_old_generation" and unauthorized["event"] == "rejected_no_authority"
        ticks = []
        quiet = []
        deadline = begin + 1_000_000_000
        while time.perf_counter_ns() < deadline:
            world.step(render=False)
            speeds = np.concatenate([arm.get_joint_velocities() for arm in arms])
            now = time.perf_counter_ns()
            tick = {"wall_perf_counter_ns": now, "sim_time_s": world.current_time,
                    "velocities_rad_s": speeds.tolist(), "queue_depth": 0, "segment_active": False}
            ticks.append(tick)
            if len(speeds) == len(all_dofs) and np.isfinite(speeds).all() and np.max(np.abs(speeds)) <= 0.01:
                if quiet and now - quiet[-1]["wall_perf_counter_ns"] > 20_000_000:
                    quiet = []
                quiet.append(tick)
                if len(quiet) >= 6 and now - quiet[0]["wall_perf_counter_ns"] >= 100_000_000:
                    break
            else:
                quiet = []
            remaining = (now + 16_000_000 - time.perf_counter_ns()) / 1e9
            if remaining > 0:
                time.sleep(remaining)
        received = time.perf_counter_ns()
        confirmed = (received <= deadline and len(quiet) >= 6
                     and quiet[-1]["wall_perf_counter_ns"] - quiet[0]["wall_perf_counter_ns"] >= 100_000_000)
        return log("rest_confirmed" if confirmed else "rest_unconfirmed", request_id=request_id,
                   last_command_id=last_command, generation=adapter.generation, reason=kind,
                   receipt_wall_perf_counter_ns=received, samples=ticks, accepted_window=quiet if confirmed else [])

    command, target = motion(0.12)
    paused = halt("pause", command, target)
    if paused["event"] == "rest_confirmed":
        adapter.authorized = True
        log("probe_resume", generation=adapter.generation, proof_request_id=paused["request_id"])
        command, target = motion(-0.12)
    halt("terminate", command, target)
    result = {"scope": "single_process_live_simulation_probe", "task_id": task,
              "channel_names_left_then_right": [dof["name"] for dof in all_dofs],
              "threshold_rad_s": 0.01, "rest_window_s": 0.10, "max_sample_gap_s": 0.02,
              "stop_deadline_s": 1.0, "events": events}
    (output / "control-evidence.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
