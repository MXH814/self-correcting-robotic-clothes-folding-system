"""Offline intake of measured component I/O; never authorizes or dispatches motion.

The camera was captured AFTER the probe command. It must not become the visual
input for that command's decision. Legacy joint ordering is not inferred here.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from .diagnostics import finite, require


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clock(value):
    require(isinstance(value, dict), "missing capture clock")
    for key in ("wall_monotonic_ns", "sim_step"):
        require(type(value.get(key)) is int and value[key] >= 0, "invalid clock: " + key)
    require(finite(value.get("sim_time_s")) and value["sim_time_s"] >= 0, "invalid sim time")
    return value


def ordered(a, b):
    return all(a[k] <= b[k] for k in ("wall_monotonic_ns", "sim_step", "sim_time_s"))


def runtime_profile(sample):
    require(sample.get("schema") == "component-runtime-io-v1", "unsupported sample schema")
    require(sample.get("stage_meters_per_unit") == 1.0 and sample.get("stage_up_axis") == "Z",
            "unsupported stage scale/axis")
    channels = []
    for side in ("left", "right"):
        dofs = sample.get(side + "_dofs")
        require(isinstance(dofs, list) and bool(dofs), "missing DOFs")
        require(all(type(d.get("index")) is int for d in dofs)
                and [d.get("index") for d in dofs] == list(range(len(dofs))), "noncontiguous DOF indices")
        names = [d.get("name") for d in dofs]
        require(all(isinstance(n, str) and n for n in names) and len(set(names)) == len(names),
                "invalid/duplicate joint names within arm")
        for d in dofs:
            require(d.get("type") == "rotation" and d.get("position_unit") == "rad"
                    and d.get("velocity_unit") == "rad/s", "unverified joint units/type")
            require(type(d.get("has_limits")) is bool, "missing limit declaration")
            require(finite(d.get("lower")) and finite(d.get("upper")) and d["lower"] < d["upper"],
                    "invalid endpoint limits")
            channels.append({"channel": side + ":" + d["name"], "arm": side,
                             "runtime_index": d["index"], "position_unit": "rad", "velocity_unit": "rad/s",
                             "has_limits": d["has_limits"], "lower": d["lower"], "upper": d["upper"]})
    identity = {"schema": "measured-component-profile/1", "channels": channels,
                "stage_meters_per_unit": 1.0, "stage_up_axis": "Z"}
    identity["profile_id"] = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()
    identity["online_authorized"] = False
    identity["legacy_joint_order_verified"] = False
    return identity


def encode_joint_target(profile, current_positions, arm, runtime_index, target_rad):
    """Encode an unexecuted one-joint proposal; endpoint checks are not DR04.

    Caller supplies a measured position vector in this exact profile order.
    Uncommanded zero entries are padding with a mask, never zero-angle commands.
    """
    channels = profile["channels"]
    require(isinstance(current_positions, list) and len(current_positions) == len(channels)
            and all(finite(x) for x in current_positions), "candidate state/profile mismatch")
    require(arm in ("left", "right") and type(runtime_index) is int, "candidate arm/index")
    matches = [i for i, d in enumerate(channels) if d["arm"] == arm and d["runtime_index"] == runtime_index]
    require(len(matches) == 1, "candidate joint absent from profile")
    index, n = matches[0], len(channels)
    d = channels[index]
    require(d["position_unit"] == "rad" and finite(target_rad), "candidate must be finite radians")
    require(not d["has_limits"] or d["lower"] <= target_rad <= d["upper"], "target outside endpoint limits")
    mask, absolute, delta = [0] * n, [0.] * n, [0.] * n
    mask[index], absolute[index], delta[index] = 1, target_rad, target_rad - current_positions[index]
    return {"schema": "masked-absolute-joint-command/1", "profile_id": profile["profile_id"],
            "commanded_channel": d["channel"], "mask": mask, "absolute_rad": absolute,
            "delta_from_measured_rad": delta, "feature_vector": mask + absolute + delta,
            "feature_order": "N-channel mask, masked absolute targets, masked deltas; N follows profile",
            "uncommanded_zero_is_padding_not_target": True,
            "validation_scope": "one-joint endpoint only; no duration, speed, collision, contact or workspace guarantee",
            "online_authorized": False}


def encode_command(sample, profile):
    cmd = sample.get("command", {})
    require(cmd.get("kind") == "absolute_joint_position_target" and cmd.get("unit") == "rad",
            "unsupported command semantics")
    require(isinstance(cmd.get("command_id"), str) and bool(cmd["command_id"]), "missing command ID")
    index = cmd.get("joint_index")
    require(type(index) is int and 0 <= index < len(sample["left_dofs"]), "invalid left joint index")
    d = sample["left_dofs"][index]
    require(cmd.get("joint_name") == d["name"], "command joint name/index mismatch")
    before = sample["observations"][0]
    q = before["left_positions"][index]
    require(finite(cmd.get("current_position_before")) and math.isclose(q, cmd["current_position_before"], abs_tol=1e-8),
            "command does not match pre-command observation")
    target = cmd.get("target")
    require(finite(target), "nonfinite target")
    require(not d["has_limits"] or d["lower"] <= target <= d["upper"], "target outside endpoint limits")
    require(ordered(before["capture_end"], clock(cmd.get("issued")))
            and ordered(cmd["issued"], clock(cmd.get("api_returned"))), "command clock order")
    if len(sample["observations"]) > 1:
        require(ordered(cmd["api_returned"], sample["observations"][1]["capture_begin"]), "feedback predates API return")
    encoded = encode_joint_target(profile, before["left_positions"] + before["right_positions"], "left", index, target)
    return {**encoded, "command_id": cmd["command_id"],
            "issued": cmd["issued"], "api_returned": cmd["api_returned"],
            "coordinator_ack": cmd.get("adapter_ack"), "executed_action_history": None,
            "recovery_candidate_label": None, "online_authorized": False}


def encode_sample(sample, history=4):
    require(type(history) is int and 1 <= history <= 64, "history must be 1..64")
    profile = runtime_profile(sample)
    observations = sample.get("observations")
    require(isinstance(observations, list) and len(observations) >= 2, "missing before/after observations")
    require(isinstance(sample.get("run_id"), str) and bool(sample["run_id"]), "missing run ID")
    vectors, rows = [], []
    previous = None
    for i, o in enumerate(observations):
        begin, end = clock(o.get("capture_begin")), clock(o.get("capture_end"))
        require(ordered(begin, end), "capture interval reversed")
        if previous is not None:
            require(ordered(previous, begin) and previous["sim_step"] < begin["sim_step"], "observation order")
        previous = end
        vector = []
        for field in ("positions", "velocities"):
            for side in ("left", "right"):
                values = o.get(side + "_" + field)
                require(isinstance(values, list) and len(values) == len(sample[side + "_dofs"])
                        and all(finite(x) for x in values), "invalid measured joint vector")
                vector.extend(values)
        past = vectors[-history:]
        padding = history - len(past)
        rows.append({"schema": "runtime-component-observation/1", "run_id": sample["run_id"], "index": i,
                     "role": "before_probe_command" if i == 0 else "after_probe_command",
                     "capture_begin": begin, "capture_end": end, "profile_id": profile["profile_id"],
                     "joint_feature": vector,
                     "joint_feature_order": "left q, right q, left dq, right dq; rad and rad/s, no fitted normalization",
                     "past_joint_feature": [0.] * (padding * len(vector)) + [x for v in past for x in v],
                     "history_mask": [False] * padding + [True] * len(past),
                     "rgb_feature": None, "executed_action_history": None,
                     "local_success": None, "autonomous_success": None, "online_authorized": False})
        vectors.append(vector)
    command = encode_command(sample, profile)
    return profile, command, rows


def camera_evidence(sample, directory, grid=8):
    import numpy as np
    from PIL import Image
    from .legacy_features import rgb_grid
    require(type(grid) is int and 1 <= grid <= 32, "grid must be 1..32")
    c = sample.get("camera", {})
    require(c.get("source") == "Isaac Sim simulated camera RGB", "unknown camera source")
    if c.get("image") is None:
        return {"status": "MISSING", "pre_command_rgb_available": False, "grid_feature": None}
    root = Path(directory).resolve()
    path = (root / c["image"]).resolve()
    require(root in path.parents, "camera path outside sample directory")
    require(path.stat().st_size <= 64 * 1024 * 1024, "camera file too large")
    with Image.open(path) as image:
        require(image.mode == "RGB" and image.size == tuple(c["configured_resolution"]), "camera image dimensions/mode")
        require(image.width * image.height <= 4096 * 4096, "camera pixels too large")
        pixels = np.asarray(image)
    require(list(pixels.shape) == c.get("shape") and c.get("dtype") == "uint8", "camera schema mismatch")
    begin, end = clock(c.get("read_begin")), clock(c.get("read_end"))
    require(ordered(begin, end), "camera read order")
    require(ordered(sample["observations"][-1]["capture_end"], begin), "camera read precedes final observation")
    minimum, maximum = int(pixels.min()), int(pixels.max())
    status = "all_black" if maximum == 0 else "uniform" if minimum == maximum else "nonuniform"
    if "rgb_status" in c:
        require(c["rgb_status"] == status and c.get("rgb_min") == minimum and c.get("rgb_max") == maximum
                and finite(c.get("rgb_std")) and math.isclose(c["rgb_std"], float(pixels.std()), abs_tol=1e-6),
                "camera pixel statistics mismatch")
    rendered = c.get("rendering_time_s")
    require(rendered is None or finite(rendered) and 0 <= rendered <= begin["sim_time_s"], "camera rendering time")
    return {"status": status, "source_sha256": digest(path), "shape": list(pixels.shape),
            "read_begin": begin, "read_end": end, "rendering_time_s": rendered,
            "age_at_read_sim_s": None if rendered is None else begin["sim_time_s"] - rendered,
            "grid_feature": rgb_grid(pixels, grid) if status == "nonuniform" else None,
            "grid": grid, "pre_command_rgb_available": False,
            "role": "post_command_inspection_only", "online_authorized": False}


def audit_control(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    require(data.get("scope") == "single_process_live_simulation_probe", "unsupported control evidence scope")
    expected = {"threshold_rad_s": .01, "rest_window_s": .1, "max_sample_gap_s": .02, "stop_deadline_s": 1.}
    require(all(data.get(k) == v for k, v in expected.items()), "unexpected probe criteria")
    n = len(data.get("channel_names_left_then_right", []))
    require(n == 60, "probe must cover 60 measured channels")
    events = data.get("events", [])
    require(bool(events) and all(e.get("task_id") == data.get("task_id") for e in events), "control task mismatch")
    times = [e.get("wall_perf_counter_ns") for e in events]
    require(all(type(t) is int and t >= 0 for t in times) and times == sorted(times), "control event order")
    cases = []
    for e in events:
        if e["event"] not in ("rest_confirmed", "rest_unconfirmed"):
            continue
        requests = [x for x in events if x["event"] == "halt_accepted" and x.get("request_id") == e.get("request_id")]
        require(len(requests) == 1, "missing/duplicate halt request")
        request = requests[0]
        require(request.get("generation") == e.get("generation") and request.get("reason") == e.get("reason")
                and request.get("last_command_id") == e.get("last_command_id"), "stop correlation mismatch")
        preceding = [x for x in events if x["wall_perf_counter_ns"] <= request["wall_perf_counter_ns"]]
        require(any(x["event"] == "probe_adapter_dispatch_ack" and x.get("command_id") == e["last_command_id"]
                    for x in preceding), "stop has no prior dispatch ACK")
        between = [x for x in events if request["wall_perf_counter_ns"] <= x["wall_perf_counter_ns"] <= e["wall_perf_counter_ns"]]
        barriers = [x for x in between if x["event"] == "probe_adapter_barrier_ack"
                    and x.get("generation") == e["generation"]]
        require(len(barriers) == 1, "missing/duplicate component generation barrier")
        require(any(x["event"] == "rejected_old_generation" and x.get("generation") < e["generation"] for x in between)
                and any(x["event"] == "rejected_no_authority" for x in between), "missing revocation probes")
        samples, window = e.get("samples", []), e.get("accepted_window", [])
        require(bool(samples), "missing stop measurements")
        for tick in samples:
            values = tick.get("velocities_rad_s")
            require(isinstance(values, list) and len(values) == n and all(finite(x) for x in values), "invalid speed channels")
            require(type(tick.get("wall_perf_counter_ns")) is int
                    and tick["wall_perf_counter_ns"] >= request["wall_perf_counter_ns"], "speed sample predates request")
        sample_times = [x["wall_perf_counter_ns"] for x in samples]
        require(all(a < b for a, b in zip(sample_times, sample_times[1:])), "speed sample order")
        require(barriers[0]["wall_perf_counter_ns"] <= sample_times[0], "speed samples precede generation barrier")
        received = e.get("receipt_wall_perf_counter_ns")
        require(type(received) is int and sample_times[-1] <= received <= e["wall_perf_counter_ns"], "receipt order")
        delay = (received - request["wall_perf_counter_ns"]) / 1e9
        span = gap = maximum = None
        if e["event"] == "rest_confirmed":
            require(len(window) >= 6 and window == samples[-len(window):], "invalid accepted window")
            ts = [x["wall_perf_counter_ns"] for x in window]
            span, gap = (ts[-1] - ts[0]) / 1e9, max(b - a for a, b in zip(ts, ts[1:])) / 1e9
            maximum = max(abs(v) for x in window for v in x["velocities_rad_s"])
            require(span >= .1 and gap <= .02 and maximum <= .01 and delay <= 1., "invalid confirmed stop conditions")
            require(all(x.get("queue_depth") == 0 and x.get("segment_active") is False for x in window), "adapter not idle")
        else:
            require(window == [], "unconfirmed stop has accepted window")
        cases.append({"reason": e["reason"], "request_id": e["request_id"], "generation": e["generation"],
                      "confirmed_in_component_probe": e["event"] == "rest_confirmed", "receipt_delay_s": delay,
                      "window_s": span, "window_samples": len(window), "max_gap_s": gap, "max_speed_rad_s": maximum})
    require(sorted(x["reason"] for x in cases) == ["pause", "terminate"], "missing/duplicate stop cases")
    return {"source_sha256": digest(path), "scope": data["scope"], "criteria": expected, "cases": cases,
            "queue_fields": "adapter declarations in a synchronous queue-free probe; no transport-queue measurement",
            "product_coordinator_verified": False, "srs_tests_accepted": False, "online_authorized": False}


def export_intake(sample_path, output, control_path=None, history=4, grid=8):
    sample_path, output = Path(sample_path).resolve(), Path(output).resolve()
    require(output != sample_path.parent and sample_path.parent not in output.parents, "output must be outside source")
    if output.exists():
        raise FileExistsError(str(output))
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    profile, command, observations = encode_sample(sample, history)
    camera = camera_evidence(sample, sample_path.parent, grid)
    control = audit_control(control_path) if control_path else None
    report = {"schema": "runtime-intake-audit/1", "source_sha256": digest(sample_path),
              "producer_sha256": digest(__file__),
              "run_id": sample["run_id"], "purpose": "offline_component_integration",
              "joint_channels": len(profile["channels"]), "observation_count": len(observations),
              "joint_feature_dimension": len(observations[0]["joint_feature"]),
              "joint_history_dimension": len(observations[0]["past_joint_feature"]),
              "command_feature_dimension": len(command["feature_vector"]), "commanded_channels": sum(command["mask"]),
              "camera": {k: v for k, v in camera.items() if k != "grid_feature"},
              "control_probe": control, "profile_id": profile["profile_id"],
              "pre_command_rgb_available": False, "executed_action_history_available": False,
              "legacy_mapping_authorized": False, "recovery_outcomes_available": False,
              "diagnostic_dataset_ready": False, "online_authorized": False, "research_conclusion": "NOT_ESTABLISHED"}
    output.mkdir(parents=True, exist_ok=False)
    payloads = {"profile.json": profile, "command.json": command, "camera.json": camera, "audit.json": report}
    for name, value in payloads.items():
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (output / "observations.jsonl").open("x", encoding="utf-8") as stream:
        for row in observations:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    manifest = {"schema": "runtime-intake-export/1", "status": "EXPORT_COMPLETE",
                "source_sha256": report["source_sha256"], "online_authorized": False,
                "files": {p.name: digest(p) for p in sorted(output.iterdir())}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", required=True)
    parser.add_argument("--output-dir", required=True, help="New directory outside source")
    parser.add_argument("--control-evidence")
    parser.add_argument("--history", type=int, default=4)
    parser.add_argument("--grid", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(export_intake(args.sample, args.output_dir, args.control_evidence, args.history, args.grid), indent=2))


if __name__ == "__main__":
    main()
