"""Import bridge for Isaac launchers whose cwd is the upstream DexGarmentLab.

No simulator initialization, network call, or motion dispatch occurs here.
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_tools.detection_runtime import DetectionRuntime
from research_tools.detection_recovery import DiagnosticRecoveryWorkflow, JsonlJournal, GeometryHoldMonitor
from research_tools.diagnostics import require


def create_runtime(*, package_dir, encoder_weights, context_reference, device="cpu"):
    return DetectionRuntime(package_dir=package_dir, encoder_weights=encoder_weights,
                            context_reference=context_reference, device=device)


def make_input(trace, observation, *, controller_phase, runtime, lineage_group=None):
    """Map actual trace clocks/IDs to the whitelist, never copy injection phase."""
    require(controller_phase in ("HOLD", "LIFT", "RELEASE", "OTHER", "VERIFY_RECOVERY"),
            "use a planned controller phase, not a fault/injection label")
    require(observation is not None and trace.observations and observation is trace.observations[-1],
            "bridge requires the actual newest observation")
    return {"trial_id": trace.trial_id, "lineage_group": lineage_group or trace.trial_id,
            "observation_id": observation["observation_id"], "frame_id": str(observation["rendering_frame"]),
            "sim_time_s": observation["rendering_time_s"],
            "read_sim_time_s": observation["camera_read_end"]["sim_time_s"],
            "phase": controller_phase, "context_reference": runtime.context_reference,
            "encoder_reference": runtime.encoder.reference if runtime.encoder is not None else "UNAVAILABLE"}


if __name__ == "__main__":
    import argparse
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--package", required=True)
    p.add_argument("--weights", required=True)
    p.add_argument("--context", required=True)
    args = p.parse_args()
    runtime = create_runtime(package_dir=args.package, encoder_weights=args.weights, context_reference=args.context)
    print(json.dumps({"schema": "pre-detection-load-check/1", "loaded": runtime.detector is not None,
                      "reason": runtime.error, "simulation_executed": False, "motion_authorized": False}))
