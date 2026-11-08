"""Causal offline features from a measured pre-action component chain.

No policy decision, clothing recovery label, product admission or motion authority
is inferred. A segment becomes history only AFTER its last measured feedback.
"""
import argparse
import json
import math
from pathlib import Path

from .diagnostics import finite, require
from .legacy_features import rgb_grid
from .runtime_intake import clock, digest, encode_sample, ordered


def verify_inventory(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    require(isinstance(manifest, dict) and 1 <= len(manifest) <= 32, "invalid chain manifest")
    require({"action-chain.json", "accepted-intent.json", "sample.json"} <= set(manifest), "missing chain artifacts")
    for name, item in manifest.items():
        path = (directory / name).resolve()
        require(directory in path.parents and path.is_file(), "artifact path outside/missing")
        require(type(item.get("size_bytes")) is int and 0 <= item["size_bytes"] <= 64 * 1024 * 1024,
                "invalid artifact size")
        require(path.stat().st_size == item["size_bytes"], "artifact size mismatch: " + name)
        require(digest(path) == item.get("sha256"), "artifact hash mismatch: " + name)
    return manifest


def read_chain(directory, grid=8):
    import numpy as np
    from PIL import Image
    directory = Path(directory).resolve()
    manifest = verify_inventory(directory)
    chain = json.loads((directory / "action-chain.json").read_text(encoding="utf-8"))
    sample = json.loads((directory / "sample.json").read_text(encoding="utf-8"))
    require(chain.get("schema") == "component-action-chain-v1"
            and chain.get("scope") == "single-process simulated component acceptance and execution", "unsupported chain")
    require(chain.get("run_id") == sample.get("run_id"), "cross-run chain")
    generation = chain.get("control_generation")
    require(type(generation) is int and generation >= 0, "invalid generation")
    profile, command, rows = encode_sample(sample)
    observation, action, execution = chain["observation"], chain["action"], chain["execution"]
    require(action == json.loads((directory / "accepted-intent.json").read_text(encoding="utf-8")), "accepted intent mismatch")
    require(isinstance(chain.get("task_id"), str) and bool(chain["task_id"])
            and chain["task_id"] == action.get("task_id"), "task identity mismatch")
    require(isinstance(observation.get("observation_id"), str) and bool(observation["observation_id"])
            and observation["observation_id"] == action.get("observation_id"), "observation identity mismatch")
    require(action.get("command_id") == execution.get("command_id") == sample["command"]["command_id"],
            "command identity mismatch")
    require(action.get("control_generation") == execution.get("control_generation") == generation, "generation mismatch")
    require(observation["joint_state"] == sample["observations"][0], "pre-action joint sample mismatch")
    require(action.get("representation") == "absolute" and action.get("unit") == "rad"
            and action.get("channel") == command["commanded_channel"]
            and action.get("runtime_index") == sample["command"]["joint_index"]
            and action.get("target") == sample["command"]["target"], "action mapping mismatch")
    binding = chain.get("joint_profile", {})
    require(binding.get("source") == "sample.json" and binding.get("sha256") == manifest["sample.json"]["sha256"],
            "profile source mismatch")
    for side in ("left", "right"):
        require(binding.get(side + "_names") == [d["name"] for d in sample[side + "_dofs"]], "profile channel order mismatch")
    require(binding.get("position_unit") == "rad" and binding.get("velocity_unit") == "rad/s", "profile unit mismatch")
    require(execution.get("segment_start") == sample["command"]["issued"]
            and execution.get("api_returned") == sample["command"]["api_returned"]
            and execution.get("measured_feedback") == sample["observations"][1:]
            and execution.get("segment_end") == sample["observations"][-1]["capture_end"], "execution feedback mismatch")
    camera = observation["camera"]
    require(camera.get("image") in manifest, "pre-action image absent from inventory")
    image_path = (directory / camera["image"]).resolve()
    require(digest(image_path) == camera.get("sha256"), "pre-action image binding mismatch")
    with Image.open(image_path) as image:
        require(image.mode == "RGB" and image.size == tuple(sample["camera"]["configured_resolution"]), "pre-action RGB shape")
        pixels = np.asarray(image)
    require(list(pixels.shape) == camera.get("shape") and pixels.dtype == np.uint8
            and pixels.min() < pixels.max(), "invalid pre-action RGB")
    camera_clocks = [clock(camera.get("read_begin")), clock(camera.get("read_end"))]
    accepted = clock(action.get("accepted"))
    seq = camera_clocks + [observation["joint_state"]["capture_begin"], observation["joint_state"]["capture_end"],
                           accepted, execution["segment_start"], execution["api_returned"]]
    require(all(ordered(a, b) for a, b in zip(seq, seq[1:])), "pre-action causal order violated")
    rendered = camera.get("rendering_time_s")
    require(finite(rendered) and 0 <= rendered <= camera_clocks[0]["sim_time_s"], "future camera rendering")
    require(isinstance(chain.get("clock_domains"), dict) and {"wall_monotonic_ns", "sim_time_s"} <= set(chain["clock_domains"]),
            "missing clock domains")
    start, end = execution["segment_start"], execution["segment_end"]
    require(type(execution.get("measured_step_delta")) is int
            and execution["measured_step_delta"] == end["sim_step"] - start["sim_step"] > 0, "execution step count mismatch")
    before, after = observation["joint_state"], execution["measured_feedback"][-1]
    measured = [b - a for side in ("left", "right")
                for a, b in zip(before[side + "_positions"], after[side + "_positions"])]
    index = sample["command"]["joint_index"]
    require(finite(execution.get("measured_joint_delta_rad"))
            and math.isclose(measured[index], execution["measured_joint_delta_rad"], abs_tol=1e-8), "measured displacement mismatch")
    visual = rgb_grid(pixels, grid)
    current = visual + rows[0]["joint_feature"] + command["feature_vector"]
    context = {"schema": "component-decision-input/1", "task_id": chain["task_id"],
               "observation_id": observation["observation_id"], "command_id": command["command_id"],
               "generation": generation, "as_of": accepted, "clock_domains": chain["clock_domains"],
               "profile_id": profile["profile_id"], "current": current,
               "block_dimensions": {"rgb_grid": len(visual), "joint_q_dq": len(rows[0]["joint_feature"]),
                                    "masked_candidate": len(command["feature_vector"])},
               "visual_history": None, "executed_action_history": None, "stage_budget": None,
               "candidate_source": "script-specified component target, not a learned decision",
               "local_success": None, "autonomous_success": None, "online_authorized": False}
    segment = {"schema": "measured-component-history-entry/1", "task_id": chain["task_id"],
               "command_id": command["command_id"], "generation": generation,
               "available_after": end, "command_feature": command["feature_vector"],
               "measured_joint_displacement_rad": measured,
               "duration_sim_s": end["sim_time_s"] - start["sim_time_s"],
               "duration_wall_s": (end["wall_monotonic_ns"] - start["wall_monotonic_ns"]) / 1e9,
               "evidence_scope": "local component acceptance plus measured segment, not product execution ACK",
               "local_success": None, "autonomous_success": None}
    report = {"schema": "preaction-intake-audit/1", "purpose": "causal_offline_component_integration",
              "source_manifest_sha256": digest(directory / "manifest.json"),
              "chain_sha256": manifest["action-chain.json"]["sha256"], "producer_sha256": digest(__file__),
              "run_id": chain["run_id"], "profile_id": profile["profile_id"],
              "verified_files": len(manifest), "current_dimension": len(current), "block_dimensions": context["block_dimensions"],
              "render_to_read_age_sim_s": camera_clocks[0]["sim_time_s"] - rendered,
              "pre_rgb_read_end_to_joint_begin_wall_s": (before["capture_begin"]["wall_monotonic_ns"] - camera_clocks[-1]["wall_monotonic_ns"]) / 1e9,
              "image_read_to_admission_wall_s": (accepted["wall_monotonic_ns"] - camera_clocks[0]["wall_monotonic_ns"]) / 1e9,
              "segment_sim_s": segment["duration_sim_s"], "segment_wall_s": segment["duration_wall_s"],
              "segment_steps": execution["measured_step_delta"], "feedback_samples": len(execution["measured_feedback"]),
              "measured_commanded_joint_delta_rad": measured[index],
              "pre_command_rgb_available": True, "prior_executed_history_for_this_decision_available": False,
              "subsequent_component_history_entry_available": True,
              "product_coordinator_verified": False, "recovery_outcomes_available": False,
              "diagnostic_dataset_ready": False, "online_authorized": False, "research_conclusion": "NOT_ESTABLISHED"}
    return context, segment, report


def history_for_decision(segment, task_id, generation, decision_clock):
    """Same-generation history only; broader continuity needs boundary evidence."""
    require(segment.get("task_id") == task_id, "history from a different task")
    require(type(generation) is int and segment.get("generation") == generation, "history generation boundary")
    require(ordered(clock(segment["available_after"]), clock(decision_clock)), "future execution history")
    return list(segment["command_feature"]) + list(segment["measured_joint_displacement_rad"]) + [
        segment["duration_sim_s"], segment["duration_wall_s"]]


def export_chain(directory, output_dir, grid=8):
    directory, output = Path(directory).resolve(), Path(output_dir).resolve()
    require(directory != output and directory not in output.parents, "output must be outside source")
    if output.exists():
        raise FileExistsError(str(output))
    context, segment, report = read_chain(directory, grid)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in {"decision-input.json": context, "executed-segment.json": segment, "audit.json": report}.items():
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    manifest = {"schema": "preaction-intake-export/1", "status": "EXPORT_COMPLETE", "online_authorized": False,
                "source_manifest_sha256": report["source_manifest_sha256"],
                "files": {p.name: digest(p) for p in sorted(output.iterdir())}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--grid", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(export_chain(args.input_dir, args.output_dir, args.grid), indent=2))


if __name__ == "__main__":
    main()
