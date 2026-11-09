"""Actual missing-package C run through the official detector and workflow.

The first pick/lift are setup under the unchanged controller. Detection is
enabled before transfer; no injection or recovery is performed in this scenario.
"""
import hashlib
import json
from pathlib import Path

from fiper_pre_evidence import FiperPreEvidence, FiperInputsUnavailable
from fold_recovery_evidence import FoldRecoveryEvidence
from fold_recovery_chain import FullRecoveryChain
from official_pre_adapter import OfficialPreAdapter


class OfficialPreEvidence(FiperPreEvidence):
    def __init__(self, output, upstream, base_env):
        FoldRecoveryEvidence.__init__(self, output, upstream, base_env)
        self.events = []
        self.record.update(injection=None, candidate=None,
                           pre_scenario="C_official_missing_package",
                           detection_entry="OfficialPreAdapter/DetectionRuntime",
                           product_stop_verified=False, final_control_state="INITIALIZING")
        repo = Path(__file__).resolve().parents[2]
        sources = [p for p in Path(__file__).parent.glob("*.py")]
        sources += list((repo / "research_tools").glob("*.py"))
        snapshot = self.output / "source-snapshot"
        hashes = {}
        for source in sources:
            relative = source.relative_to(repo)
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            hashes[relative.as_posix()] = hashlib.sha256(target.read_bytes()).hexdigest()
        (self.output / "official-pre-config.json").write_text(json.dumps({
            "schema": "official-pre-run/1", "trial_id": self.record["trial_id"],
            "scenario": self.record["pre_scenario"], "producer_sha256": hashes,
            "package_condition": "explicitly absent local paths; no synthetic scores",
            "detection_enabled_at": "before first left transfer after normal pick and lift",
            "independent_review": "pending"}, indent=2), encoding="utf-8")

    def attach(self, env):
        self.env = env
        left = env.bimanual_dex.dexleft
        original = left.dense_step_action
        self.chain = FullRecoveryChain(self, env, self.upstream)
        # Unique absent paths make the missing-package experiment reproducible.
        self.adapter = OfficialPreAdapter(
            self.chain.trace, package_dir=self.output / "absent-detector-package",
            encoder_weights=self.output / "absent-encoder.pth",
            context_reference=self.chain.context_ref,
            journal_path=self.output / "official-workflow-events.jsonl")
        count = 0

        def move(target_pos, target_ori=None, *args, **kwargs):
            nonlocal count
            count += 1
            if count == 3:
                self.chain.phase = "normal-left-transfer"
                obs = self.chain.trace.observe(self.chain.phase, force=True)
                metadata, report, request = self.adapter.observe(
                    obs, controller_phase="HOLD", expected_holding=True)
                self.event("OFFICIAL_DETECTION", observation=metadata, report=report, request=request)
                if (report["status"] != "UNKNOWN"
                        or request["kind"] != "REQUEST_HALT_AND_HELP"):
                    raise RuntimeError("Missing-package C must request halt and help")
                self.record.update(final_control_state="HELP_REQUESTED_AUTOMATIC_DISPATCH_DISABLED",
                                   fiper_report=report, dispatch_count_at_help=len(self.chain.trace.actions),
                                   recovery_attempts=0, fixed_continuation_started=False)
                self.event("HELP_REQUESTED", reason=report["reason"],
                           automatic_dispatch_enabled=False, physical_rest_confirmed=False,
                           manual_authority_granted=False)
                self.snapshot(env, "help-requested")
                self.save()
                raise FiperInputsUnavailable(report["reason"])
            return original(target_pos, target_ori, *args, **kwargs)

        left.dense_step_action = move
