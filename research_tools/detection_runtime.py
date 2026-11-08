"""Small RGB-to-report entry point for the simulator adapter. No Isaac dependency."""
import time

from .diagnostics import finite, require
from .observation_detector import FIELDS, METHOD, OnlineObservationDetector, load_package


class DetectionRuntime:
    """Missing weights/calibration or incompatible context remains UNKNOWN.

    Construct once per run, call observe for unique frames. The caller must pass
    an actual camera-read wall clock; replay instead uses the offline score CLI.
    Neither this object nor its report authorizes or dispatches robot motion.
    """
    def __init__(self, *, package_dir, encoder_weights, context_reference, device="cpu"):
        self.context_reference = context_reference
        self.encoder, self.detector, self.error = None, None, None
        try:
            from .detection_encoder import FrozenRGBEncoder
            self.encoder = FrozenRGBEncoder(encoder_weights, device)
            model, meta = load_package(package_dir, encoder_reference=self.encoder.reference,
                                       context_reference=context_reference, device=device)
            self.detector = OnlineObservationDetector(model, meta, device=device)
        except (OSError, ValueError, KeyError, RuntimeError, ImportError) as error:
            self.error = str(error)

    def observe(self, rgb, observation, *, generation, captured_wall_s, now_wall_s=None):
        started = time.monotonic()
        now_wall_s = started if now_wall_s is None else now_wall_s
        report = {"schema": "observation-deviation-report/1", "method": METHOD, "status": "UNKNOWN",
                  "reason": "MODEL_OR_CALIBRATION_UNAVAILABLE", "generation": generation,
                  "trial_id": observation.get("trial_id") if isinstance(observation, dict) else None,
                  "observation_id": observation.get("observation_id") if isinstance(observation, dict) else None,
                  "captured_wall_s": captured_wall_s, "decision_wall_s": now_wall_s,
                  "context_reference": self.context_reference, "failure_class": None,
                  "failure_probability": None, "raw_score": None, "score": None, "threshold": None,
                  "motion_authorized": False, "diagnostic_detail": self.error}
        if self.detector is None:
            return report
        try:
            require(isinstance(observation, dict) and set(observation) == FIELDS - {"embedding"}, "INVALID_INPUT_METADATA")
            require(observation["context_reference"] == self.context_reference, "CONTEXT_MISMATCH")
            require(finite(now_wall_s) and finite(captured_wall_s)
                    and 0 <= now_wall_s - captured_wall_s <= 1, "STALE_OBSERVATION")
            require(rgb is not None, "MISSING_RGB")
            embedding = self.encoder.encode([rgb])[0].tolist()
            row = dict(observation, embedding=embedding)
            effective_now = now_wall_s + time.monotonic() - started
            report = self.detector.detect(row, generation=generation, captured_wall_s=captured_wall_s,
                                          now_wall_s=effective_now)
            report["end_to_end_processing_wall_s"] = time.monotonic() - started
            return report
        except (ValueError, TypeError, KeyError, RuntimeError) as error:
            self.detector.reset()
            report.update(reason=str(error), decision_wall_s=now_wall_s + time.monotonic() - started)
            return report
