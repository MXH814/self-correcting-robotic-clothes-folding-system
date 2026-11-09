"""Summarize committed runtime logs, not RGB inference or product acceptance.

Every input is checked against the portable inventory before use. All timings
are measured values recorded by the producer; no replay clock, injection label
or final point count is used as a failure-detection ground truth.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics


def read(path):
    return json.loads(path.read_bytes())


def summary(values):
    if not values:
        return {"count": 0, "min_s": None, "median_s": None, "p95_s": None, "max_s": None}
    if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("Invalid recorded timing")
    values = sorted(values)
    position = .95 * (len(values) - 1)
    lower, upper = math.floor(position), math.ceil(position)
    p95 = values[lower] + (values[upper] - values[lower]) * (position - lower)
    return dict(count=len(values), min_s=values[0], median_s=statistics.median(values),
                p95_s=p95, max_s=values[-1])


def analyze(root):
    root = root.resolve()
    inventory = {entry["file"]: entry for entry in read(root / "portable-manifest.json")["files"]}
    sources = {}

    def checked(relative):
        path = root / relative
        entry = inventory[relative]
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if len(content) != entry["bytes"] or digest != entry["sha256"]:
            raise ValueError("Portable source changed: " + relative)
        sources[relative] = digest
        return path

    model = read(checked("model/manifest.json"))
    result = {"schema": "pre-recorded-runtime-summary/1", "cases": {},
        "package_id": model["package_id"], "phase_thresholds": model["phase_thresholds"],
        "scope": "recorded producer timings and event order; no new inference or simulation",
        "timing_definition": "end_to_end_processing_wall_s is DetectionRuntime.observe internal processing only",
        "excluded_from_timing": ["camera exposure", "unmeasured transport/worker queues", "UI", "product stop acceptance"],
        "statistical_performance_claim": None, "full_rgb_scores_recomputed": False,
        "srs_quality_accepted": False}
    for case in ("A", "B", "C"):
        lines = checked(case + "/pre-demo-events.jsonl").read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in lines]
        record = read(checked(case + "/full-fold-recovery.json"))
        detections = [event for event in events if event["kind"] == "OFFICIAL_DETECTION"]
        if any(event["trial_id"] != record["trial_id"] for event in events):
            raise ValueError("Cross-trial event")
        reports = [event["report"] for event in detections]
        if any(report.get("replay") is True for report in reports):
            raise ValueError("Offline replay is not a recorded online timing")
        for report in reports:
            if report["status"] in ("NORMAL", "ANOMALY") and report["package_id"] != model["package_id"]:
                raise ValueError("Mixed detector package")
        measurements = [report["end_to_end_processing_wall_s"] for report in reports
                        if "end_to_end_processing_wall_s" in report]
        ages = [report["decision_wall_s"] - report["captured_wall_s"] for report in reports]
        output = dict(trial_id=record["trial_id"], reports=len(reports),
            status_counts=dict(Counter(report["status"] for report in reports)),
            phase_counts=dict(Counter(event["observation"]["phase"] for event in detections)),
            internal_processing=summary(measurements), read_to_decision=summary(ages),
            recovery_attempts=record.get("recovery_attempts", 0), final_state=record["final_control_state"])
        final = next((event for event in events if event["kind"] == "FINAL_OUTCOME"), None)
        output["final_sim_s"] = final["clock"]["sim_time_s"] if final else None
        alert = next((event for event in detections if event.get("request")
                      and event["request"]["kind"] == "REQUEST_RECOVERY_PREFLIGHT"), None)
        if alert:
            macro = record["macro_execution"]
            refresh = next(event for event in events if event["kind"] == "PREFLIGHT_REDETECTION")
            first_dispatch = macro[0]["begin"]
            output["first_alert"] = dict(observed_sim_s=alert["report"]["observed_sim_s"],
                decision_wall_s=alert["report"]["decision_wall_s"],
                observation_id=alert["report"]["observation_id"])
            output["preflight_refresh"] = dict(observed_sim_s=refresh["report"]["observed_sim_s"],
                captured_wall_s=refresh["report"]["captured_wall_s"],
                decision_wall_s=refresh["report"]["decision_wall_s"],
                observation_id=refresh["report"]["observation_id"], kind=refresh["request"]["kind"])
            output["macro_begin_sim_s"] = first_dispatch["sim_time_s"]
            output["first_alert_decision_to_macro_begin_wall_s"] = (
                first_dispatch["wall_monotonic_ns"] / 1e9 - alert["report"]["decision_wall_s"])
            output["refreshed_image_read_to_macro_begin_wall_s"] = (
                first_dispatch["wall_monotonic_ns"] / 1e9 - refresh["report"]["captured_wall_s"])
            output["macro_duration_sim_s"] = macro[-1]["end"]["sim_time_s"] - first_dispatch["sim_time_s"]
            output["macro_duration_wall_s"] = (
                macro[-1]["end"]["wall_monotonic_ns"] - first_dispatch["wall_monotonic_ns"]) / 1e9
            output["detection_delay_ground_truth_s"] = None
            output["delay_note"] = "No independent human anomaly-onset label; injection time is not that label"
            if not 0 <= output["refreshed_image_read_to_macro_begin_wall_s"] <= 1:
                raise ValueError("Recorded preflight image was not fresh at macro start")
        result["cases"][case] = output
    result["verified_input_sha256"] = sources
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.root)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("Saved recorded timing summary for A/B/C; full RGB inference remains unverified.")
