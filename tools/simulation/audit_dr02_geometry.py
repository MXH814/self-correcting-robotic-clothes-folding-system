"""Audit fingertip proximity and fixed material IDs without assigning DR02 truth."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull


def window_indices(rows, phase):
    indices = [i for i, row in enumerate(rows) if row["stream"] == "window" and row["phase"] == phase]
    if len(indices) < 2:
        raise ValueError(f"Missing window: {phase}")
    times = np.array([rows[i]["sim_time_s"] for i in indices])
    gaps = np.diff(times)
    if times[-1] - times[0] < 0.2 or np.any((gaps <= 0) | (gaps > 0.100001)):
        raise ValueError(f"Invalid DR02 window: {phase}")
    return indices


def torso_width(settled):
    # Proposed cross-sections for this particular TCLC_018 asset, pending landmark review.
    spans = {}
    for name, from_hem_m in (("shoulder", 0.52), ("hem", 0.04)):
        y = float(settled[:, 1].min() + from_hem_m)
        ids = np.flatnonzero(np.abs(settled[:, 1] - y) <= 0.005)
        ends = ids[[np.argmin(settled[ids, 0]), np.argmax(settled[ids, 0])]]
        spans[name] = {"strip_y_m": y, "strip_half_width_m": 0.005, "endpoint_vertex_ids": ends.tolist(),
                       "endpoint_world_m": settled[ends].tolist(),
                       "width_m": float(np.diff(settled[ends, 0])[0])}
    return {"spans": spans, "w0_m": (spans["shoulder"]["width_m"] + spans["hem"]["width_m"]) / 2}


def pad_margins(cloth, tips, matrices, equations):
    midpoint = tips[:, 3, :3].mean(axis=0)
    nearby = np.flatnonzero(np.linalg.norm(cloth - midpoint, axis=1) <= 0.12)
    score = np.full(len(cloth), np.inf)
    if nearby.size == 0:
        return score
    margins = []
    for matrix, planes in zip(matrices, equations):
        inverse_basis = np.linalg.inv(matrix[:3, :3])
        local = (cloth[nearby] - matrix[3, :3]) @ inverse_basis
        world_normal_length = np.linalg.norm(inverse_basis @ planes[:, :3].T, axis=0)
        margins.append(((local @ planes[:, :3].T + planes[:, 3]) / world_normal_length).max(axis=1))
    score[nearby] = np.max(margins, axis=0)
    return score


def audit(root, reference):
    meta = json.loads((root / "dr02-samples.json").read_text(encoding="utf-8"))
    fault = json.loads((root / "fault-evidence.json").read_text(encoding="utf-8"))
    trial, = fault["trials"]
    if trial["trial_id"] != meta["trial_id"] or trial["status"] != "completed":
        raise ValueError("Mismatched or incomplete physical trial")
    with np.load(root / "dr02-samples.npz", allow_pickle=False) as data:
        cloth = data["cloth_world_m"]
        tips = data["tip_local_to_world"]
        matrices = data["collider_local_to_world"]
        rgb = data["rgb"]
        equations = [ConvexHull(data[entry["points"]]).equations for entry in meta["colliders"]]
    if len(equations) != 2 or not all(np.isfinite(array).all() for array in (cloth, tips, matrices)):
        raise ValueError("Expected two distal mesh colliders and finite cloth geometry")
    rows = meta["phase_samples"]
    if not len(rows) == len(cloth) == len(tips) == len(matrices):
        raise ValueError("Sample arrays are not aligned")
    w0 = torso_width(reference)
    threshold = 0.012
    windows = {}
    margin_by_index = {}
    phases = ["closed", "lifted", "hold", "transferred", "planned_release"]
    if any(row["phase"] == "disturbance_closed_hand" and row["stream"] == "window" for row in rows):
        phases.insert(2, "disturbance_closed_hand")
    for phase in phases:
        indices = window_indices(rows, phase)
        for i in indices:
            margin_by_index[i] = pad_margins(cloth[i], tips[i], matrices[i], equations)
        margins = np.array([margin_by_index[i] for i in indices])
        frame_ids = [rows[i]["frame_index"] for i in indices]
        if any(frame_id is None or not 0 <= frame_id < len(rgb) for frame_id in frame_ids):
            raise ValueError(f"Missing RGB index in {phase}")
        if any(rows[i]["rendering_time_s"] is None
               or rows[i]["rendering_time_s"] > rows[i]["sim_time_s"] + 1e-7 for i in indices):
            raise ValueError(f"RGB render time falls after the physical sample in {phase}")
        best = margins.min(axis=1)
        windows[phase] = {"indices": indices,
                          "span_sim_s": rows[indices[-1]]["sim_time_s"] - rows[indices[0]]["sim_time_s"],
                          "near_both_pad_counts": (margins <= threshold).sum(axis=1).tolist(),
                          "best_margin_m": [float(v) if np.isfinite(v) else None for v in best],
                          "rgb_frame_std": [float(rgb[i].std()) for i in frame_ids]}
    lifted = windows["lifted"]["indices"]
    lifted_scores = np.array([margin_by_index[i] for i in lifted])
    ids = np.flatnonzero((lifted_scores <= threshold).all(axis=0))
    if ids.size:
        ids = ids[np.argsort(np.median(lifted_scores[:, ids], axis=0))[:6]]
    patch = None
    if ids.size:
        canonical = reference[ids].mean(axis=0)
        expected = reference[meta["expected_patch_ids"]].mean(axis=0)
        centers = cloth[:, ids, :].mean(axis=1)
        relative = []
        for tip in range(2):
            local = (centers[:, None, :] - tips[:, tip, 3, :3][:, None, :]) @ np.linalg.inv(tips[:, tip, :3, :3])
            local = local[:, 0, :]
            baseline = np.median(local[lifted], axis=0)
            relative.append(np.linalg.norm(local - baseline, axis=1))
        held = windows["hold"]["indices"]
        patch = {"vertex_ids": ids.tolist(), "reference_patch_center_m": canonical.tolist(),
                 "reference_expected_center_m": expected.tolist(),
                 "reference_offset_xy_m": float(np.linalg.norm((canonical - expected)[:2])),
                 "lifted_to_held_displacement_m_by_finger": np.array(relative)[:, held].tolist(),
                 "hold_vertex_ids_near_both": [[int(vertex) for vertex in ids
                                                if margin_by_index[i][vertex] <= threshold] for i in held],
                 "hold_all_vertex_ids_near_both": [np.flatnonzero(margin_by_index[i] <= threshold).tolist()
                                                   for i in held]}
    return {"trial_id": trial["trial_id"], "condition": trial["condition"], "width": w0,
            "offset_threshold_m": 0.05 * w0["w0_m"], "slip_threshold_m": 0.04 * w0["w0_m"],
            "both_pad_margin_band_m": threshold, "windows": windows, "fixed_lifted_patch": patch,
            "proximity_method": "maximum signed supporting-plane margin of distal collider convex hulls",
            "native_contact_report": None, "dr02_label": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial", type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    args = parser.parse_args()
    with np.load(args.reference, allow_pickle=False) as source:
        reference = source["vertices_m"]
    print(json.dumps(audit(args.trial, reference), indent=2, allow_nan=False))
