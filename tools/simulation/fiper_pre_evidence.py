"""Actual simulator check of the missing-FIPER-input refusal branch (Z2 C only)."""
import hashlib
import json
import time
from pathlib import Path

from fold_recovery_evidence import FoldRecoveryEvidence
from fold_recovery_chain import FullRecoveryChain
from fiper_input_gate import FIPER_COMMIT, check_fiper_inputs
from pre_runtime_bridge import PreRuntimeBridge


class FiperInputsUnavailable(RuntimeError):
    pass


class FiperPreEvidence(FoldRecoveryEvidence):
    def __init__(self, output, upstream, base_env):
        super().__init__(output, upstream, base_env)
        self.record.update(injection=None, candidate=None, pre_scenario="C_actual_missing_fiper_inputs",
                           detection_method="FIPER-RND-OE-observation-adaptation", official_commit=FIPER_COMMIT,
                           product_stop_verified=False, final_control_state="INITIALIZING")
        self.events = []
        source_names = ("fiper_pre_evidence.py", "fiper_input_gate.py", "pre_runtime_bridge.py", "fold_recovery_chain.py",
                        "fold_recovery_evidence.py", "garment_observation_trace.py", "run_fold_local.py")
        config = {"schema": "fiper-pre-adapter/1", "trial_id": self.record["trial_id"],
                  "scenario": "C_actual_missing_fiper_inputs", "detector_executed": False,
                  "shared_research_context_compatible": False,
                  "producer_sha256": {n: hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                                      for n in source_names}}
        (self.output / "fiper-pre-config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    def event(self, kind, **payload):
        item = {"schema": "pre-demo-event/1", "sequence": len(self.events),
                "trial_id": self.record["trial_id"], "kind": kind, "source": "actual_simulation",
                "clock": self.chain.trace.clock(), **payload}
        self.events.append(item)
        with (self.output / "pre-demo-events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, allow_nan=False) + "\n")
            stream.flush()

    def attach(self, env):
        self.env = env
        left = env.bimanual_dex.dexleft
        original = left.dense_step_action
        self.chain = FullRecoveryChain(self, env, self.upstream)
        count = 0

        def move(target_pos, target_ori=None, *args, **kwargs):
            nonlocal count
            count += 1
            if count == 3:
                # The first pick and lift completed; inspect genuinely available inputs.
                self.chain.phase = "fiper-input-check"
                obs = self.chain.trace.observe(self.chain.phase, force=True)
                packet = {"trial_id": self.record["trial_id"], "observation_id": obs["observation_id"],
                          "observation_clock": obs["joint_read_end"],
                          "frame_index": obs["frame_index"], "joint_state": obs["joint_state"],
                          "encoder_ref": None, "preprocessing_ref": None, "obs_embeddings": None,
                          "rnd_checkpoint_ref": None, "calibration_ref": None,
                          "feature_source": "RGB available; Ma encoder not loaded"}
                self.event("OBSERVATION_AVAILABLE", packet=packet)
                report = check_fiper_inputs(packet)
                self.event("DETECTION_UNAVAILABLE", report=report, decision_wall_monotonic_ns=time.monotonic_ns())
                bridge = PreRuntimeBridge(emit=lambda e: self.event("CONTROL_BRIDGE", control_event=e))
                route = bridge.handle({"trial_id": self.record["trial_id"],
                    "observation_id": obs["observation_id"], "capture_clock": obs["joint_read_end"],
                    "phase": self.chain.phase}, expected_hold=True)
                if route != "HELP_NO_NEW_DISPATCH":
                    raise RuntimeError("This entry supports only the unavailable-input C branch")
                self.record.update(final_control_state="HELP_REQUESTED_AUTOMATIC_DISPATCH_DISABLED",
                                   fiper_report=report, dispatch_count_at_help=len(self.chain.trace.actions),
                                   recovery_attempts=0, fixed_continuation_started=False)
                self.event("HELP_REQUESTED", reason=report["reason"], missing=report["missing"],
                           automatic_dispatch_enabled=False, physical_rest_confirmed=False,
                           manual_authority_granted=False)
                self.snapshot(env, "help-requested")
                self.save()
                raise FiperInputsUnavailable(";".join(report["missing"]))
            return original(target_pos, target_ori, *args, **kwargs)

        left.dense_step_action = move

    def abort(self, error):
        if not isinstance(error, FiperInputsUnavailable):
            self.record["final_control_state"] = "EXECUTION_ERROR"
        super().abort(error)
        if self.chain is not None:
            self.record["dispatch_count_at_exit"] = len(self.chain.trace.actions)
        self.save()
        files = [{"file": p.name, "bytes": p.stat().st_size,
                  "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(self.output.iterdir()) if p.is_file() and p.name != "manifest.json"]
        (self.output / "manifest.json").write_text(json.dumps({"trial_id": self.record["trial_id"],
            "scope": "incomplete_pre_demo_missing_fiper_inputs", "files": files}, indent=2), encoding="utf-8")
