"""Software fixtures test causal monitoring and integration, NOT robot accuracy."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

from research_tools.detection_encoder import preprocess, file_hash
from research_tools.detection_recovery import DiagnosticRecoveryWorkflow, GeometryHoldMonitor, JsonlJournal, OPERATIONS
from research_tools.detection_runtime import DetectionRuntime
from research_tools.observation_detector import (OnlineObservationDetector, empirical_threshold,
                                                fit, load_package, validate_partitions, windowed, METHOD)
from third_party.fiper.rnd_observation import ObservationRND


def row(i, value=0., *, trial="fixture-t", phase="HOLD"):
    return dict(trial_id=trial, lineage_group=trial, observation_id=f"obs-{i}", frame_id=str(i),
                sim_time_s=i * .1, read_sim_time_s=i * .1 + .01, phase=phase, context_reference="fixture-context",
                encoder_reference="fixture-encoder", embedding=[value] + [0.] * 511)


def metadata():
    return dict(window=3, max_gap_s=.15, allowed_phases=["HOLD"], threshold=1.,
                package_id="fixture-package", context_reference="fixture-context", encoder_reference="fixture-encoder")


class ScoreModel(torch.nn.Module):
    def forward(self, x):
        return x[:, 0].abs()


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.previous_threads = torch.get_num_threads()
        torch.set_num_threads(2)
        self.d = OnlineObservationDetector(ScoreModel(), metadata())

    def tearDown(self):
        torch.set_num_threads(self.previous_threads)

    def detect(self, r, generation=0, now=.5, captured=.5):
        return self.d.detect(r, generation=generation, captured_wall_s=captured, now_wall_s=now)

    def test_causal_window_and_report_semantics(self):
        self.assertEqual(self.detect(row(0, 2.))["reason"], "WINDOW_WARMUP")
        self.assertEqual(self.detect(row(1, 2.))["status"], "UNKNOWN")
        result = self.detect(row(2, 2.))
        self.assertEqual(result["status"], "ANOMALY")
        self.assertEqual(result["score"], 2.)
        self.assertIsNone(result["failure_class"])
        self.assertIsNone(result["failure_probability"])
        self.assertFalse(result["motion_authorized"])

    def test_bad_or_stale_input_resets_window(self):
        self.detect(row(0))
        result = self.detect(row(1), now=2., captured=0.)
        self.assertEqual(result["reason"], "STALE_OBSERVATION")
        self.assertEqual(len(self.d.history), 0)
        self.assertEqual(self.detect(row(2))["reason"], "WINDOW_WARMUP")

    def test_duplicate_cannot_fill_window(self):
        self.detect(row(0))
        self.assertEqual(self.detect(row(0))["reason"], "DUPLICATE_OR_REORDERED_FRAME")
        self.assertEqual(len(self.d.history), 0)

    def test_generation_trial_phase_and_gap_restart_window(self):
        for i in range(3): self.detect(row(i))
        self.assertEqual(self.detect(row(3), generation=1)["reason"], "WINDOW_WARMUP")
        self.assertEqual(self.detect(row(4, phase="RELEASE"), generation=1)["reason"], "UNSUPPORTED_PHASE")
        self.assertEqual(self.detect(row(8, trial="fixture-new"), generation=1)["reason"], "WINDOW_WARMUP")
        self.assertEqual(self.detect(row(12, trial="fixture-new"), generation=1)["reason"], "WINDOW_WARMUP")

    def test_context_nan_and_privileged_field_rejected(self):
        for bad, reason in [(dict(row(0), context_reference="other"), "CONTEXT_MISMATCH"),
                            (dict(row(0), embedding=[float("nan")] * 512), "INVALID_EMBEDDING"),
                            (dict(row(0), injection=True), "INVALID_SCHEMA")]:
            self.assertEqual(self.detect(bad)["reason"], reason)

    def test_online_window_matches_calibration_window(self):
        rows = [row(i, float(i % 3)) for i in range(9)]
        offline = windowed(rows, [r["embedding"][0] for r in rows], 3, .15, ["HOLD"])
        online = [self.detect(r)["score"] for r in rows]
        self.assertEqual(online, offline)

    def test_unsupported_phase_clears_offline_calibration(self):
        rows = [row(i, phase="RELEASE" if i == 3 else "HOLD") for i in range(7)]
        values = windowed(rows, [0.] * 7, 3, .15, ["HOLD"])
        self.assertEqual(values, [None, None, 0., None, None, None, 0.])

    def test_model_runtime_is_included_in_expiry(self):
        with patch("research_tools.observation_detector.time.monotonic", side_effect=[0., 2.]):
            result = self.detect(row(0))
        self.assertEqual(result["reason"], "DETECTION_RUNTIME_EXPIRED")

    def test_old_renderer_frame_is_not_fresh_just_because_read_now(self):
        result = self.detect(dict(row(0), read_sim_time_s=5.))
        self.assertEqual(result["reason"], "STALE_OR_FUTURE_CAMERA_FRAME")

    def test_missing_package_runtime_never_authorizes_motion(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = DetectionRuntime(package_dir=Path(temp)/"missing", encoder_weights=Path(temp)/"missing.pth",
                                       context_reference="fixture-context")
            result = runtime.observe(None, row(0), generation=0, captured_wall_s=.5, now_wall_s=.5)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertFalse(result["motion_authorized"])

    def test_isaac_bridge_uses_actual_frame_and_does_not_copy_fault_phase(self):
        from tools.simulation.pre_detection_bridge import make_input
        from types import SimpleNamespace
        obs = dict(observation_id="fixture", rendering_frame=5, rendering_time_s=.5,
                   camera_read_end={"sim_time_s": .51}, phase="injected-open")
        trace = SimpleNamespace(trial_id="fixture", observations=[obs])
        runtime = SimpleNamespace(context_reference="fixture-context", encoder=SimpleNamespace(reference="fixture-encoder"))
        result = make_input(trace, obs, controller_phase="HOLD", runtime=runtime)
        self.assertEqual(result["phase"], "HOLD")
        self.assertEqual(result["read_sim_time_s"], .51)
        self.assertNotIn("injected-open", result.values())

    def test_isaac_bridge_rejects_reused_frame_or_injection_phase(self):
        from tools.simulation.pre_detection_bridge import make_input
        from types import SimpleNamespace
        old = dict(observation_id="old")
        trace = SimpleNamespace(observations=[dict(observation_id="new")])
        with self.assertRaisesRegex(ValueError, "newest"):
            make_input(trace, old, controller_phase="HOLD", runtime=None)
        with self.assertRaisesRegex(ValueError, "controller phase"):
            make_input(trace, old, controller_phase="injected-open", runtime=None)

    def test_preprocessing_shape_and_channels(self):
        image = np.zeros((240, 320, 3), dtype=np.uint8)
        image[:, :, 0] = 255
        out = preprocess(image)
        self.assertEqual(tuple(out.shape), (3, 224, 224))
        self.assertAlmostEqual(out[0, 0, 0].item(), (1-.485)/.229, places=5)
        self.assertAlmostEqual(out[1, 0, 0].item(), -.456/.224, places=5)

    def test_upstream_network_factories_target_freezing_and_loss(self):
        model = ObservationRND(512, output_dim=8, initialize=False)
        self.assertEqual([m.out_features for m in model.target_network if isinstance(m, torch.nn.Linear)],
                         [1024, 2048, 4096, 8])
        self.assertEqual([m.out_features for m in model.predictor_network if isinstance(m, torch.nn.Linear)],
                         [1024, 2048, 4096, 2048, 1024, 8])
        self.assertTrue(all(not p.requires_grad for p in model.target_network.parameters()))
        x = torch.ones(1, 512)
        score = model(x)
        self.assertTrue(torch.allclose(score, torch.nn.functional.pairwise_distance(
            model.predictor_network(x), model.target_network(x), p=2)))
        score.mean().backward()
        self.assertTrue(any(p.grad is not None for p in model.predictor_network.parameters()))
        self.assertTrue(all(p.grad is None for p in model.target_network.parameters()))


def partitions(root):
    result = {}
    for split, trial in [("fit", "fixture-fit"), ("calibration", "fixture-calibration")]:
        file = root / (split + ".jsonl")
        file.write_text("\n".join(json.dumps(row(i, .01*i, trial=trial)) for i in range(7)) + "\n")
        result[split] = [dict(features=str(file), feature_sha256=file_hash(file), source_reference="fixture-source-"+split,
                              normal_review=True, review_reference="SOFTWARE FIXTURE ONLY")]
    return result


class PartitionAndPackageTests(unittest.TestCase):
    def test_cross_split_sources_and_context_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            parts = partitions(Path(temp))
            validate_partitions(parts, ["HOLD"])
            bad = copy.deepcopy(parts)
            bad["calibration"] = bad["fit"]
            with self.assertRaisesRegex(ValueError, "lineage"):
                validate_partitions(bad, ["HOLD"])
            bad = copy.deepcopy(parts)
            bad["calibration"][0]["normal_review"] = False
            with self.assertRaisesRegex(ValueError, "normal trial"):
                validate_partitions(bad, ["HOLD"])
            with self.assertRaisesRegex(ValueError, "phases"):
                validate_partitions(parts, ["UNSPECIFIED"])

    def test_empirical_threshold_not_framewise_quantile(self):
        self.assertEqual(empirical_threshold([1., 10.], .95), 10.)
        with self.assertRaises(ValueError): empirical_threshold([], .95)

    def test_full_network_fit_calibrate_save_load_and_context_binding(self):
        previous = torch.get_num_threads()
        torch.set_num_threads(2)
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                meta = fit(partitions(root), root/"package", phases=["HOLD"], epochs=1, batch_size=8,
                           output_dim=8, window=3)
                self.assertFalse(meta["online_authorized"])
                self.assertIsNone(meta["statistical_guarantee"])
                model, restored = load_package(root/"package", encoder_reference="fixture-encoder",
                                               context_reference="fixture-context")
                self.assertEqual(restored["package_id"], meta["package_id"])
                self.assertTrue(torch.isfinite(model(torch.zeros(1, 512))).all())
                with self.assertRaisesRegex(ValueError, "context mismatch"):
                    load_package(root/"package", encoder_reference="other", context_reference="fixture-context")
        finally:
            torch.set_num_threads(previous)


class RecoveryFlowTests(unittest.TestCase):
    def report(self, status="ANOMALY", i="obs", generation=0):
        return dict(trial_id="fixture-t", generation=generation, observation_id=i, status=status,
                    reason="OBSERVATION_OOD", captured_wall_s=0., decision_wall_s=.1,
                    schema="observation-deviation-report/1", method=METHOD, motion_authorized=False,
                    package_id="fixture-package", context_reference="fixture-context",
                    raw_score=2. if status == "ANOMALY" else 0.,
                    score=2. if status == "ANOMALY" else 0., threshold=1.)

    def flow(self, **kwargs):
        return DiagnosticRecoveryWorkflow("fixture-t", detector_package_id="fixture-package",
                                          context_reference="fixture-context", **kwargs)

    def permit(self):
        return dict(trial_id="fixture-t", generation=0, authority=True, measured_rest=True,
                    queue_empty=True, macro_validated=True, now_wall_s=.2)

    def request(self, flow):
        return flow.on_detection(self.report(), now_wall_s=.2, expected_holding=True)

    def test_normal_and_planned_release_do_not_request_macro(self):
        flow = self.flow()
        self.assertEqual(flow.on_detection(self.report("NORMAL"), now_wall_s=.2, expected_holding=True)["kind"], "CONTINUE")
        self.assertEqual(flow.on_detection(self.report(i="next"), now_wall_s=.2, expected_holding=False)["kind"], "NO_RECOVERY")
        self.assertEqual(flow.attempts, 0)

    def test_unknown_requests_halt_not_blind_recovery(self):
        flow = DiagnosticRecoveryWorkflow("fixture-t")
        self.assertEqual(flow.on_detection(self.report("UNKNOWN"), now_wall_s=.2,
                                          expected_holding=True)["kind"], "REQUEST_HALT_AND_HELP")
        self.assertEqual(flow.attempts, 0)

    def test_unconfirmed_rest_and_missing_journal_block_execution(self):
        for permit in [dict(self.permit(), measured_rest=False), self.permit()]:
            flow = self.flow()
            request = self.request(flow)
            self.assertEqual(flow.begin_macro(request["request_id"], permit=permit)["kind"], "REQUEST_HALT_AND_HELP")
            self.assertEqual(flow.attempts, 0)

    def test_journal_failure_prevents_acceptance(self):
        def fail(event):
            if event["kind"] == "MACRO_ACCEPTED": raise OSError("fixture disk failure")
        flow = self.flow(journal=fail)
        request = self.request(flow)
        with self.assertRaises(OSError): flow.begin_macro(request["request_id"], permit=self.permit())
        self.assertEqual(flow.attempts, 0)
        self.assertEqual(flow.state, "RECOVERY_REQUESTED")

    def test_complete_flow_requires_post_macro_measurement_and_new_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"events.jsonl"
            flow = self.flow(journal=JsonlJournal(path))
            request = self.request(flow)
            accepted = flow.begin_macro(request["request_id"], permit=self.permit())
            self.assertEqual(accepted["kind"], "MACRO_ACCEPTED")
            self.assertEqual(flow.attempts, 1)
            self.assertEqual(flow.begin_macro(request["request_id"], permit=self.permit())["kind"], "REJECT")
            flow.finish_macro(request["request_id"], operations=OPERATIONS, feedback_complete=True, finish_sim_s=2.)
            monitor = GeometryHoldMonitor(table_z_m=0., min_cloth_height_m=.04, max_hand_distance_m=.1)
            for i in range(3):
                report = monitor.update(trial_id="fixture-t", generation=0, observation_id=str(i), frame_id=str(i),
                                        sim_time_s=2.1+i*.1, hand_xyz_m=[0,0,.2], cloth_xyz_m=[0,0,.18],
                                        provenance="privileged_sim_material_patch", phase="VERIFY_RECOVERY",
                                        captured_wall_s=10+i*.1, now_wall_s=10+i*.1)
                result = flow.verify(report, now_wall_s=10+i*.1)
            self.assertEqual(result["kind"], "REQUEST_FIXED_CONTINUATION")
            self.assertEqual(flow.generation, 1)
            self.assertEqual(flow.state, "RUNNING")
            self.assertEqual(self.request(flow)["kind"], "REJECT")
            self.assertIn("MACRO_ACCEPTED", path.read_text())

    def test_old_verification_and_incomplete_macro_do_not_resume(self):
        flow = self.flow(journal=lambda event: None)
        request = self.request(flow)
        flow.begin_macro(request["request_id"], permit=self.permit())
        result = flow.finish_macro(request["request_id"], operations=["lift"], feedback_complete=True, finish_sim_s=2.)
        self.assertEqual(result["kind"], "REQUEST_HALT_AND_HELP")

    def test_verification_cannot_reuse_pre_macro_window(self):
        flow = self.flow(journal=lambda event: None)
        request = self.request(flow)
        flow.begin_macro(request["request_id"], permit=self.permit())
        flow.finish_macro(request["request_id"], operations=OPERATIONS, feedback_complete=True, finish_sim_s=2.)
        result = flow.verify(dict(trial_id="fixture-t", generation=0, observation_id="new", frame_id="new",
                                  status="HELD", method="task-conditioned-hold-geometry/1",
                                  observed_sim_s=2.2, window_start_sim_s=1.9,
                                  captured_wall_s=10., decision_wall_s=10.,
                                  schema="geometry-hold-report/1", motion_authorized=False), now_wall_s=10.)
        self.assertEqual(result["reason"], "VERIFICATION_WINDOW_OVERLAPS_MACRO")

    def test_revoke_invalidates_old_permit(self):
        flow = self.flow(journal=lambda event: None)
        request = self.request(flow)
        flow.revoke()
        self.assertEqual(flow.begin_macro(request["request_id"], permit=self.permit())["kind"], "REJECT")
        self.assertEqual(flow.attempts, 0)

    def test_expired_preflight_does_not_consume_attempt(self):
        flow = self.flow(journal=lambda event: None)
        request = self.request(flow)
        result = flow.begin_macro(request["request_id"], permit=dict(self.permit(), now_wall_s=2.))
        self.assertEqual(result["reason"], "PREFLIGHT_REPORT_EXPIRED")
        self.assertEqual(flow.attempts, 0)

    def test_wrong_package_or_inconsistent_score_does_not_trigger_macro(self):
        for altered in [dict(self.report(), package_id="other"), dict(self.report(), score=0.),
                        dict(self.report(), schema="other")]:
            result = self.flow().on_detection(altered, now_wall_s=.2, expected_holding=True)
            self.assertEqual(result["kind"], "REQUEST_HALT_AND_HELP")

    def test_geometry_needs_sustained_fresh_observations(self):
        monitor = GeometryHoldMonitor(table_z_m=0., min_cloth_height_m=.04, max_hand_distance_m=.1)
        def update(i):
            return monitor.update(trial_id="fixture-t", generation=0, observation_id=str(i), frame_id=str(i),
                                  sim_time_s=i*.1, hand_xyz_m=[0,0,.2], cloth_xyz_m=[0,0,.01],
                                  provenance="privileged_sim_material_patch", phase="HOLD",
                                  captured_wall_s=i*.1, now_wall_s=i*.1)
        self.assertEqual(update(0)["status"], "UNKNOWN")
        self.assertEqual(update(1)["status"], "UNKNOWN")
        self.assertEqual(update(2)["status"], "LOST")
        self.assertEqual(update(2)["reason"], "DUPLICATE_OR_REORDERED_FRAME")


if __name__ == "__main__":
    unittest.main()
