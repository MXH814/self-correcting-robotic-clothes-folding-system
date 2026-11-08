"""Reproduce the Pre observation-only pilot on whole, fingerprinted trials."""
import argparse
import hashlib
import json
import time
from tempfile import TemporaryDirectory
from pathlib import Path

import numpy as np
from PIL import Image
import torch

from .detection_recovery import DiagnosticRecoveryWorkflow
from .detection_runtime import DetectionRuntime
from .detection_encoder import FrozenRGBEncoder
from .observation_detector import windowed
from third_party.fiper.rnd_observation import ObservationRND
from .legacy_observations import digest

UPSTREAM = "13d79c5c3069def843e454787ff128defc249838"
CONFIG = Path(__file__).resolve().parents[1] / "configs/research/pre-observation-rnd-v1.json"
SEED, WINDOW, STEPS = 17, 5, 40


def make_model():
    torch.set_num_threads(2)
    torch.manual_seed(SEED)
    return ObservationRND(512, 128).eval()


def initial_hash(model):
    h = hashlib.sha256()
    for tensor in model.state_dict().values():
        h.update(tensor.detach().contiguous().numpy().tobytes())
    return h.hexdigest()


def fit(model, features):
    x = torch.tensor(features)
    head = model.predictor_network[-1]
    with torch.no_grad():
        target = model.target_network(x)
        hidden = model.predictor_network[:-1](x)
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.001)
    losses = []
    for step in range(STEPS):
        optimizer.zero_grad()
        loss = torch.nn.functional.pairwise_distance(head(hidden), target).mean()
        loss.backward()
        optimizer.step()
        losses.append(loss.item())
    return losses


def load_head(path, profile, encoder_reference):
    saved = torch.load(path, map_location="cpu", weights_only=True)
    model = make_model()
    if (saved["profile"] != profile or saved["initial_sha256"] != initial_hash(model)
            or saved["encoder_reference"] != encoder_reference or saved["revision"] != UPSTREAM):
        raise ValueError("Checkpoint profile, network initialization or source differs")
    model.predictor_network[-1].load_state_dict(saved["head"])
    return model


def read_trial(entry, root):
    path = root / entry["path"]
    uid = entry["trial_id"]
    mp = path / "manifest.json"
    if digest(mp) != entry["manifest_sha256"]:
        raise ValueError(f"Wrong source manifest: {mp}")
    manifest = json.loads(mp.read_bytes())
    hashes = {f["file"]: f["sha256"] for f in manifest["files"]}

    def checked(filename):
        if digest(path / filename) != hashes[filename]:
            raise ValueError(f"Fingerprint mismatch: {filename}")
        return path / filename

    trace = json.loads(checked("observation-trace.json").read_bytes())
    if uid != manifest["trial_id"] or uid != trace["trial_id"]:
        raise ValueError("Trial ID mismatch")
    with np.load(checked("rgb-frames.npz"), allow_pickle=False) as data:
        rgb = data["rgb"]
    unique = {}
    for obs in trace["observations"]:
        idx = obs["frame_index"]
        unique.setdefault(idx, dict(frame=idx, phase=obs["phase"], id=obs["observation_id"],
                                    t=obs["rendering_time_s"], read=obs["camera_read_end"]["sim_time_s"]))
        unique[idx].setdefault("observation_ids", []).append(obs["observation_id"])
        unique[idx]["last_read"] = obs["camera_read_end"]["sim_time_s"]
    if list(unique) != list(range(len(rgb))) or np.any(np.diff([x["t"] for x in unique.values()]) <= 0):
        raise ValueError("Frames and render times must increase")
    events = []
    if entry["group"] == "full":
        record = json.loads(checked("full-fold-recovery.json").read_bytes())
        commands = {item["command_id"]: item for item in trace["actions"]}
        obs_ids = {o["observation_id"] for o in trace["observations"]}
        for op in record["macro_execution"]:
            ids = op["command_ids"]
            if not ids or any(commands[i]["feedback_observation_id"] not in obs_ids for i in ids):
                raise ValueError("Macro dispatch lacks feedback")
            events.append(dict(kind="macro", name=op["operation"], t=op["begin"]["sim_time_s"],
                               end=op["end"]["sim_time_s"], dispatches=len(ids)))
        for name, cp in record["checkpoints"].items():
            events.append(dict(kind="checkpoint", name=name, t=cp["sim_time_s"],
                               height_mm=(1000*cp["intended_patch_xyz_m"][2]
                                          if cp.get("intended_patch_xyz_m") else None)))
        events.append(dict(kind="region", name="final", t=record["checkpoints"]["final"]["sim_time_s"],
                           **record["judgment"]))
    return rgb, list(unique.values()), sorted(events, key=lambda e: e["t"])


def check_missing_package(trial, rgb, rows, weights):
    """Replay the missing-package branch on a real image; no simulator dispatch."""
    context = "pre-detection-context#sha256=45a3fe13bcdfcb7df82f930d7322ae3dc6c5d331d1a3246669b53c70becf2c30"
    with TemporaryDirectory() as temporary:
        runtime = DetectionRuntime(package_dir=Path(temporary)/"absent", encoder_weights=weights,
                                   context_reference=context)
        # Before-injection checkpoint from the existing #24 evidence, used only to select a review frame.
        row = min(rows, key=lambda r: abs(r["t"]-5.95))
        observation = dict(trial_id=trial["trial_id"], observation_id=row["id"])
        report = runtime.observe(rgb[row["frame"]], observation, generation=0, captured_wall_s=time.monotonic())
        flow = DiagnosticRecoveryWorkflow(trial["trial_id"], context_reference=context)
        event = flow.on_detection(report, now_wall_s=time.monotonic(), expected_holding=True)
    if report["status"] != "UNKNOWN" or event["kind"] != "REQUEST_HALT_AND_HELP":
        raise RuntimeError("Missing package did not produce the expected safe request")
    return dict(source="offline software replay with deliberately absent package", frame=row["frame"],
                t=row["t"], trial_id=trial["trial_id"], observation_id=row["id"],
                status=report["status"], detector_reason=report["reason"], workflow_event=event,
                simulator_executed=False, device_rest_confirmed=None, user_assistance_confirmed=None)


def save_atlas(rgb, path):
    width, height = 160, 120
    sheet = Image.new("RGB", (10*width, ((len(rgb)+9)//10)*height))
    for i, pixels in enumerate(rgb):
        sheet.paste(Image.fromarray(pixels).resize((width, height), Image.Resampling.LANCZOS),
                    ((i % 10)*width, (i // 10)*height))
    sheet.save(path, quality=79)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--weights", type=Path, required=True)
    for group in ("first", "near", "full"):
        parser.add_argument("--" + group, type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination.exists():
        parser.error("choose a new output directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as scratch:
        out = Path(scratch) / "export"
        out.mkdir()
        export(args, out)
        out.rename(destination)


def export(args, out):
    torch.set_num_threads(2)
    encoder = FrozenRGBEncoder(args.weights)
    cfg = json.loads(args.config.read_bytes())
    runs, vectors, ids = [], {}, set()
    for trial in cfg["trials"]:
        if trial["role"] == "excluded":
            continue
        uid, key = trial["trial_id"], trial["key"]
        if uid in ids:
            raise ValueError("Trial reused across roles: " + uid)
        ids.add(uid)
        rgb, rows, events = read_trial(trial, getattr(args, trial["group"]))
        if list(rgb.shape[1:]) != cfg["profiles"][trial["profile"]]["hw"] + [3] or rgb.dtype != np.uint8:
            raise ValueError(f"Incompatible RGB: {key}")
        if trial["role"] != "evidence_only":
            vectors[key] = np.concatenate([encoder.encode(rgb[i:i+8]) for i in range(0,len(rgb),8)])
        if key == "full-recovery":
            fallback = check_missing_package(trial, rgb, rows, args.weights)
            (out/"missing-package.json").write_text(json.dumps(fallback, indent=2)+"\n", encoding="utf8")
        save_atlas(rgb, out / (key + ".jpg"))
        runs.append({**trial, "rows": rows, "events": events, "threshold": None})
        del rgb

    report = {"upstream": UPSTREAM, "torch": str(torch.__version__), "seed": SEED,
              "window": WINDOW, "fit_steps": STEPS, "profiles": {}}
    profile = "first-sleeve-fixed"
    domain = [r for r in runs if r["profile"] == profile]
    model = make_model()
    init = initial_hash(model)
    fit_run, = [r for r in domain if r["role"] == "fit"]
    # Fit only the final predictor layer. This interim package cannot authorize the online detector.
    fit_mask = [r["phase"] in {"expected_hold_begins", "lift", "fixed_transfer"} for r in fit_run["rows"]]
    losses = fit(model, vectors[fit_run["key"]][fit_mask])
    checkpoint = out / (profile + ".pt")
    with checkpoint.open("wb") as stream:
        torch.save(dict(head=model.predictor_network[-1].state_dict(), initial_sha256=init,
                        encoder_reference=encoder.reference, profile=profile, revision=UPSTREAM), stream)
    model = load_head(checkpoint, profile, encoder.reference)
    for run in domain:
        with torch.no_grad():
            raw = model(torch.from_numpy(vectors[run["key"]])).tolist()
        # Diagnostic whole-rollout curve, independent of injected or scripted phase names.
        clock = [{"phase": "OBSERVATION", "sim_time_s": row["t"]} for row in run["rows"]]
        scores = windowed(clock, raw, WINDOW, 0.25)
        for row, value, average in zip(run["rows"], raw, scores, strict=True):
            row.update(raw=value, score=average, alarm=None)
    report["profiles"][profile] = dict(fit=fit_run["trial_id"], losses=losses, threshold=None,
                                       fit_frames=sum(fit_mask), calibrated_on=[], encoder_reference=encoder.reference,
                                       initial_sha256=init, checkpoint_sha256=digest(checkpoint))
    (out/"run.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf8")
    # JS wrapper permits opening the trace directly from disk without fetch or a server.
    (out/"trials.js").write_text("const evidenceTrials = "+json.dumps(runs, separators=(",", ":"), allow_nan=False)+";\n",
                                 encoding="utf8")
    print([(r["key"], r["role"], len(r["rows"])) for r in runs])


if __name__ == "__main__":
    main()
