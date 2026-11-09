"""Matched normal RGB collection for the RND-OE adapter, with recovery disabled."""
import hashlib
import json
import os
from pathlib import Path

from fold_recovery_evidence import FoldRecoveryEvidence
from fold_recovery_chain import FullRecoveryChain


class PreObservationEvidence(FoldRecoveryEvidence):
    def __init__(self, output, upstream, base_env):
        super().__init__(output, upstream, base_env)
        self.record.update(injection=None, candidate=None, collection_mode="normal_controller_only",
                           recovery_enabled=False, detector_status="UNKNOWN", detector_loaded=False,
                           final_control_state="COLLECTING", independent_review_status="pending")
        self.events = []
        sources = ("pre_observation_evidence.py", "fold_recovery_chain.py", "fold_recovery_evidence.py",
                   "garment_observation_trace.py", "run_fold_local.py", "run_local.ps1")
        config = {"schema": "rnd-oe-observation-collection/1", "trial_id": self.record["trial_id"],
                  "controller": "unchanged upstream GAM plus scripted Fold Tops demonstration",
                  "fault_injection": False, "recovery_enabled": False,
                  "detector_method_target": "FIPER RND-OE observation branch adaptation",
                  "encoder": None, "rnd_model": None, "threshold": None,
                  "producer_sha256": {n: hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                                      for n in sources},
                  "dataset_use": "unassigned; split whole trials after independent intake review"}
        (self.output / "pre-observation-config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    def event(self, kind, **payload):
        entry = {"schema": "pre-demo-event/1", "sequence": len(self.events),
                 "trial_id": self.record["trial_id"], "kind": kind, "source": "actual_simulation",
                 "clock": self.chain.trace.clock(), **payload}
        self.events.append(entry)
        with (self.output / "pre-demo-events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, allow_nan=False) + "\n")

    def attach(self, env):
        self.chain = FullRecoveryChain(self, env, self.upstream)
        robot = env.bimanual_dex
        for side, arm in (("left", robot.dexleft), ("right", robot.dexright)):
            original = arm.dense_step_action
            counter = [0]

            def move(target_pos, target_ori=None, *args, _side=side, _original=original,
                     _counter=counter, **kwargs):
                _counter[0] += 1
                # Names describe controller intent, not a detected grasp success.
                label = {1: "approach-pick", 2: "lift", 3: "transfer"}.get(_counter[0], "scripted-move")
                self.chain.phase = f"normal-{_side}-{label}"
                self.chain.trace.boundary(self.chain.phase)
                self.event("NORMAL_ACTION_BEGIN", arm=_side, operation=label,
                           target_world_m=target_pos.tolist(), expected_hold=label in ("lift", "transfer"))
                result = _original(target_pos, target_ori, *args, **kwargs)
                self.event("NORMAL_ACTION_END", arm=_side, operation=label, sdk_result=bool(result))
                return result

            arm.dense_step_action = move
        original_hand = robot.set_both_hand_state

        def hand(*args, **kwargs):
            left = kwargs.get("left_hand_state", args[0] if args else "None")
            right = kwargs.get("right_hand_state", args[1] if len(args) > 1 else "None")
            if "open" in (left, right):
                self.chain.phase = "normal-planned-release"
                self.chain.trace.boundary(self.chain.phase)
            self.event("NORMAL_HAND_COMMAND", left=left, right=right,
                       planned_release="open" in (left, right))
            return original_hand(*args, **kwargs)

        robot.set_both_hand_state = hand
        self.event("COLLECTION_STARTED", detector_status="UNKNOWN", recovery_enabled=False)

    def finish(self, env):
        if env is None or self.record["judgment"] is None:
            self.abort(RuntimeError("Normal collection did not reach final judgment"))
            return
        self.chain.phase = "final-evidence"
        self.chain.trace.boundary(self.chain.phase)
        if self.chain.trace.pending_feedback:
            raise RuntimeError("Pending action feedback at normal collection end")
        self.snapshot(env, "final")
        self.event("FINAL_OUTCOME", upstream_region_proxy=self.record["judgment"],
                   srs_quality=None, anomaly_label=None)
        self.record["final_control_state"] = "NORMAL_COLLECTION_COMPLETED"
        self.chain.trace.save("normal_no_injection", scope="complete_fold_tops_normal_collection")
        self.save()
        files = [{"file": p.name, "bytes": p.stat().st_size,
                  "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(self.output.iterdir()) if p.is_file() and p.name != "manifest.json"]
        (self.output / "manifest.json").write_text(json.dumps({"trial_id": self.record["trial_id"],
            "scope": "complete_fold_tops_normal_collection", "files": files}, indent=2), encoding="utf-8")
        marker = os.environ.get("ROBOTICS_PROBE_MARKER")
        if marker:
            Path(marker).write_text(str(self.output), encoding="utf-8")
        print("NORMAL_OBSERVATION_CAPTURED", self.output, flush=True)
