"""Contract-level substitution at the actual Pre adapter entry point."""
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/simulation"))
from official_pre_adapter import OfficialPreAdapter
from research_tools.observation_detector import METHOD


class DetectorSubstitutionTest(unittest.TestCase):
    def test_reports_cross_the_same_adapter_and_workflow(self):
        cases = (
            ("NORMAL", None, METHOD, "CONTINUE"),
            ("ANOMALY", None, METHOD, "REQUEST_RECOVERY_PREFLIGHT"),
            ("UNKNOWN", "WINDOW_WARMUP", METHOD, "WAIT_FOR_OBSERVATION"),
            ("UNKNOWN", "MODEL_OR_CALIBRATION_UNAVAILABLE", METHOD, "REQUEST_HALT_AND_HELP"),
            ("NORMAL", None, "independent-detector/1", "REQUEST_HALT_AND_HELP"),
        )
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        observation = dict(observation_id="obs", frame_index=0, rendering_frame=1,
                           rendering_time_s=1.0, camera_read_end={"sim_time_s": 1.0})
        trace = SimpleNamespace(trial_id="trial", frames=[frame], observations=[observation])
        for status, reason, method, expected in cases:
            with self.subTest(status=status, reason=reason, method=method), tempfile.TemporaryDirectory() as temp:
                observation["camera_read_begin"] = {"wall_monotonic_ns": time.monotonic_ns()}
                runtime = Mock(context_reference="context")
                runtime.detector.meta = {"package_id": "substitute"}
                runtime.encoder.reference = "fixture-encoder"

                def observe(rgb, metadata, *, generation, captured_wall_s, now_wall_s):
                    self.assertIs(rgb, frame)
                    self.assertEqual(metadata["observation_id"], "obs")
                    self.assertEqual(metadata["phase"], "HOLD")
                    score = {"NORMAL": 0.0, "ANOMALY": 2.0, "UNKNOWN": None}[status]
                    return dict(schema="observation-deviation-report/1", method=method,
                                trial_id=metadata["trial_id"], observation_id=metadata["observation_id"],
                                generation=generation, captured_wall_s=captured_wall_s,
                                decision_wall_s=now_wall_s, package_id="substitute",
                                context_reference=metadata["context_reference"], status=status, reason=reason,
                                motion_authorized=False, score=score, raw_score=score, threshold=1.0)

                runtime.observe.side_effect = observe
                with patch("official_pre_adapter.create_runtime", return_value=runtime):
                    adapter = OfficialPreAdapter(trace, package_dir=temp, encoder_weights=None,
                                                 context_reference="context", journal_path=Path(temp) / "events.jsonl")
                _, report, event = adapter.observe(observation, controller_phase="HOLD", expected_holding=True)
                self.assertEqual(event["kind"], expected)
                self.assertFalse(report["motion_authorized"])
                self.assertEqual(adapter.flow.attempts, 0)
                if method != METHOD:
                    self.assertEqual(event["reason"], "INVALID_DETECTION_REPORT")


if __name__ == "__main__":
    unittest.main()
