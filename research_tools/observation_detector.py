"""FIPER RND-OE adaptation: normal-only fitting, independent calibration, causal scoring.

This is NOT complete FIPER, a DR02 classifier, a probability estimate, or motion
authorization. Uses attributed upstream network factories; preprocessing,
episode-max empirical calibration, package format and online lifecycle are ours.
"""
import argparse
from collections import deque
import json
import math
from pathlib import Path
import time

from .diagnostics import finite, require
from .shared_context import content_hash

METHOD = "fiper-rnd-oe-resnet18-adaptation/1"
FIELDS = {"trial_id", "lineage_group", "observation_id", "frame_id", "sim_time_s", "read_sim_time_s", "phase",
          "context_reference", "encoder_reference", "embedding"}
NUMERIC_FIELDS = {"sim_time_s", "read_sim_time_s", "embedding"}


def read_features(path):
    with Path(path).open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    require(bool(rows), "empty features")
    for r in rows:
        require(set(r) == FIELDS, "feature schema: no injection/outcome/extra input fields allowed")
        require(all(isinstance(r[k], str) and r[k] for k in FIELDS - NUMERIC_FIELDS), "missing identity")
        require(finite(r["sim_time_s"]) and r["sim_time_s"] >= 0, "invalid observation time")
        require(finite(r["read_sim_time_s"]) and 0 <= r["read_sim_time_s"] - r["sim_time_s"] <= 1,
                "stale/future camera frame")
        require(isinstance(r["embedding"], list) and len(r["embedding"]) == 512
                and all(finite(v) for v in r["embedding"]), "expected finite 512-D embedding")
    return rows


def validate_partitions(partitions, allowed_phases):
    """A normal review is a declaration with provenance, not automatic truth."""
    require(set(partitions) == {"fit", "calibration"}, "fit and calibration partitions required")
    require(bool(allowed_phases) and "UNSPECIFIED" not in allowed_phases, "controller phases must be specified")
    identities, references, results = {}, set(), {}
    for split, items in partitions.items():
        require(isinstance(items, list) and bool(items), "no " + split + " trials")
        results[split] = []
        for item in items:
            require(item.get("normal_review") is True and isinstance(item.get("review_reference"), str)
                    and bool(item["review_reference"].strip()), "reviewed normal trial declaration required")
            rows = read_features(item["features"])
            require(len({r["trial_id"] for r in rows}) == 1 and len({r["lineage_group"] for r in rows}) == 1,
                    "one complete trial/family per feature file")
            require(item.get("source_reference") and item.get("feature_sha256"), "source and feature hash required")
            from .detection_encoder import file_hash
            require(file_hash(item["features"]) == item["feature_sha256"], "feature hash mismatch")
            for prefix, value in (("trial:", rows[0]["trial_id"]), ("family:", rows[0]["lineage_group"]),
                                  ("source:", item["source_reference"]), ("features:", item["feature_sha256"])):
                key = prefix + value
                require(key not in identities, "duplicate/cross-partition trial or source lineage")
                identities[key] = split
            keys, last = set(), -math.inf
            for r in rows:
                require(r["sim_time_s"] > last and r["frame_id"] not in keys, "duplicate/out-of-order frame")
                last = r["sim_time_s"]
                keys.add(r["frame_id"])
                references.add((r["encoder_reference"], r["context_reference"]))
            selected = [r for r in rows if r["phase"] in allowed_phases]
            require(bool(selected), "trial has no supported controller phase")
            results[split].append(rows)
    require(len(references) == 1, "mixed encoder or sensor/controller context")
    return results, next(iter(references))


def model_scores(model, rows, device="cpu", batch_size=64):
    import torch
    scores = []
    with torch.inference_mode():
        for i in range(0, len(rows), batch_size):
            x = torch.tensor([r["embedding"] for r in rows[i:i + batch_size]], dtype=torch.float32, device=device)
            scores.extend(model(x).cpu().tolist())
    require(all(finite(v) and v >= 0 for v in scores), "invalid RND scores")
    return scores


def windowed(rows, scores, window, max_gap_s, allowed_phases=None):
    history = deque(maxlen=window)
    previous = None
    result = []
    for row, score in zip(rows, scores):
        if allowed_phases is not None and row["phase"] not in allowed_phases:
            history.clear()
            previous = None
            result.append(None)
            continue
        if previous is not None and (row["phase"] != previous["phase"]
                                    or row["sim_time_s"] - previous["sim_time_s"] > max_gap_s):
            history.clear()
        history.append(score)
        result.append(sum(history) / window if len(history) == window else None)
        previous = row
    return result


def empirical_threshold(trial_maxima, quantile):
    """Empirical higher quantile of per-trial maxima; NO CP guarantee claimed."""
    require(bool(trial_maxima) and all(finite(x) and x >= 0 for x in trial_maxima), "invalid calibration maxima")
    require(finite(quantile) and 0 < quantile < 1, "invalid empirical quantile")
    values = sorted(trial_maxima)
    return values[math.ceil((len(values) - 1) * quantile)]


def fit(partitions, output, *, phases, epochs=10, batch_size=64, learning_rate=1e-4,
        seed=17, window=5, max_gap_s=.25, quantile=.95, output_dim=128, device="cpu"):
    """Train predictor only; calibration uses disjoint normal trial maxima."""
    import torch
    from third_party.fiper.rnd_observation import ObservationRND
    require(type(epochs) is int and epochs > 0 and type(batch_size) is int and batch_size > 0, "invalid training budget")
    require(finite(learning_rate) and learning_rate > 0, "invalid learning rate")
    require(type(window) is int and window >= 1 and finite(max_gap_s) and max_gap_s > 0, "invalid window")
    output = Path(output)
    require(not output.exists(), "detector output already exists")
    groups, (encoder_reference, context_reference) = validate_partitions(partitions, phases)
    rows = [r for trial in groups["fit"] for r in trial if r["phase"] in phases]
    # Keep global RNG state unchanged outside this fitting operation.
    cuda_devices = [torch.device(device).index or 0] if torch.device(device).type == "cuda" else []
    with torch.random.fork_rng(devices=cuda_devices):
        torch.manual_seed(seed)
        model = ObservationRND(512, output_dim).to(device)
        optimizer = torch.optim.AdamW(model.predictor_network.parameters(), lr=learning_rate, weight_decay=1e-5)
        generator = torch.Generator().manual_seed(seed)
        data = torch.tensor([r["embedding"] for r in rows], dtype=torch.float32)
        losses = []
        for _ in range(epochs):
            total = 0.
            for indices in torch.randperm(len(data), generator=generator).split(batch_size):
                loss = model(data[indices].to(device)).mean()
                require(bool(torch.isfinite(loss)), "nonfinite fitting loss")
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total += loss.item() * len(indices)
            losses.append(total / len(data))
    model.eval()
    maxima = []
    for trial in groups["calibration"]:
        values = windowed(trial, model_scores(model, trial, device), window, max_gap_s, phases)
        values = [v for v in values if v is not None]
        require(bool(values), "calibration trial has no complete causal window")
        maxima.append(max(values))
    threshold = empirical_threshold(maxima, quantile)
    metadata = {"schema": "observation-detector-package/1", "method": METHOD, "trained": True,
                "encoder_reference": encoder_reference, "context_reference": context_reference,
                "input_dim": 512, "output_dim": output_dim, "allowed_phases": list(phases),
                "window": window, "max_gap_s": max_gap_s, "threshold": threshold,
                "threshold_method": "empirical-higher-quantile-of-trial-window-maxima/1",
                "quantile": quantile, "calibration_trial_maxima": maxima, "normal_data": partitions,
                "training": {"epochs": epochs, "batch_size": batch_size, "lr": learning_rate,
                             "seed": seed, "predictor_l2_losses": losses},
                "failure_probability": None, "statistical_guarantee": None,
                "full_fiper": False, "online_authorized": False}
    metadata["package_id"] = content_hash(metadata)
    output.mkdir(parents=True)
    path = output / "detector.pt"
    torch.save({"metadata": metadata, "state_dict": model.cpu().state_dict()}, path)
    from .detection_encoder import file_hash
    metadata_export = dict(metadata, checkpoint_sha256=file_hash(path))
    (output / "manifest.json").write_text(json.dumps(metadata_export, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return metadata_export


def load_package(directory, *, encoder_reference, context_reference, device="cpu"):
    import torch
    from third_party.fiper.rnd_observation import ObservationRND
    from .detection_encoder import file_hash
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    require(file_hash(root / "detector.pt") == manifest["checkpoint_sha256"], "checkpoint binding mismatch")
    package = torch.load(root / "detector.pt", map_location="cpu", weights_only=True)
    meta = package["metadata"]
    require(meta == {k: v for k, v in manifest.items() if k != "checkpoint_sha256"}, "manifest/model metadata mismatch")
    require(meta.get("schema") == "observation-detector-package/1" and meta.get("method") == METHOD
            and meta.get("trained") is True and meta.get("full_fiper") is False, "invalid detector package")
    identity = {k: v for k, v in meta.items() if k != "package_id"}
    require(content_hash(identity) == meta["package_id"], "package identity mismatch")
    require(meta["encoder_reference"] == encoder_reference and meta["context_reference"] == context_reference,
            "encoder or sensor/controller context mismatch")
    require(finite(meta["threshold"]) and meta["threshold"] >= 0
            and type(meta["window"]) is int and meta["window"] >= 1
            and finite(meta["max_gap_s"]) and meta["max_gap_s"] > 0, "invalid detection settings")
    model = ObservationRND(512, meta["output_dim"], initialize=False)
    model.load_state_dict(package["state_dict"], strict=True)
    model.requires_grad_(False).eval().to(device)
    require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), "nonfinite detector parameters")
    return model, meta


class OnlineObservationDetector:
    """Fresh-frame causal monitor. Outputs reports only; no robot SDK dependency."""
    def __init__(self, model, metadata, *, max_age_wall_s=1., device="cpu"):
        self.model, self.meta, self.device = model, metadata, device
        self.max_age_wall_s = max_age_wall_s
        self.history = deque(maxlen=metadata["window"])
        self.last = None

    def reset(self):
        self.history.clear()
        self.last = None

    def detect(self, row, *, generation, captured_wall_s, now_wall_s):
        started = time.monotonic()
        report = {"schema": "observation-deviation-report/1", "method": METHOD, "status": "UNKNOWN",
                  "reason": "INVALID_INPUT", "observation_id": row.get("observation_id") if isinstance(row, dict) else None,
                  "trial_id": row.get("trial_id") if isinstance(row, dict) else None,
                  "generation": generation, "raw_score": None, "score": None,
                  "threshold": self.meta["threshold"], "package_id": self.meta["package_id"],
                  "context_reference": self.meta["context_reference"], "observed_sim_s": None,
                  "captured_wall_s": captured_wall_s, "decision_wall_s": now_wall_s,
                  "failure_class": None, "failure_probability": None, "motion_authorized": False}
        try:
            require(type(generation) is int and generation >= 0, "INVALID_GENERATION")
            require(isinstance(row, dict) and set(row) == FIELDS, "INVALID_SCHEMA")
            require(all(isinstance(row[k], str) and row[k]
                        for k in FIELDS - NUMERIC_FIELDS), "INVALID_IDENTITY")
            require(finite(captured_wall_s) and finite(now_wall_s)
                    and 0 <= now_wall_s - captured_wall_s <= self.max_age_wall_s, "STALE_OBSERVATION")
            require(row["encoder_reference"] == self.meta["encoder_reference"]
                    and row["context_reference"] == self.meta["context_reference"], "CONTEXT_MISMATCH")
            require(self.model is not None, "MODEL_UNAVAILABLE")
            require(row["phase"] in self.meta["allowed_phases"], "UNSUPPORTED_PHASE")
            require(finite(row["sim_time_s"]) and row["sim_time_s"] >= 0, "INVALID_TIME")
            require(finite(row["read_sim_time_s"]) and 0 <= row["read_sim_time_s"] - row["sim_time_s"] <= 1,
                    "STALE_OR_FUTURE_CAMERA_FRAME")
            require(isinstance(row["embedding"], list) and len(row["embedding"]) == 512
                    and all(finite(x) for x in row["embedding"]), "INVALID_EMBEDDING")
            key = (row["trial_id"], generation, row["phase"])
            if self.last is not None:
                last_key, last_frame, last_time = self.last
                if key != last_key:
                    self.history.clear()
                else:
                    require(row["frame_id"] != last_frame and row["sim_time_s"] > last_time, "DUPLICATE_OR_REORDERED_FRAME")
                    if row["sim_time_s"] - last_time > self.meta["max_gap_s"]:
                        self.history.clear()
            raw = model_scores(self.model, [row], self.device)[0]
            self.history.append(raw)
            self.last = (key, row["frame_id"], row["sim_time_s"])
            report.update(raw_score=raw, observed_sim_s=row["sim_time_s"])
            if len(self.history) < self.meta["window"]:
                report["reason"] = "WINDOW_WARMUP"
            else:
                score = sum(self.history) / len(self.history)
                report.update(score=score, status="ANOMALY" if score > self.meta["threshold"] else "NORMAL",
                              reason="OBSERVATION_OOD" if score > self.meta["threshold"] else "WITHIN_NORMAL_REFERENCE")
        except (ValueError, KeyError, TypeError) as error:
            self.reset()
            report["reason"] = str(error)
        elapsed = time.monotonic() - started
        report.update(processing_wall_s=elapsed)
        if finite(now_wall_s):
            report["decision_wall_s"] = now_wall_s + elapsed
            if report["raw_score"] is not None and finite(captured_wall_s) and report["decision_wall_s"] - captured_wall_s > self.max_age_wall_s:
                self.reset()
                report.update(status="UNKNOWN", reason="DETECTION_RUNTIME_EXPIRED")
        return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    train = sub.add_parser("fit")
    train.add_argument("--partitions", required=True)
    train.add_argument("--output", required=True)
    train.add_argument("--phase", action="append", required=True)
    train.add_argument("--epochs", type=int, default=10)
    train.add_argument("--device", default="cpu")
    score = sub.add_parser("score")
    for name in ("package", "input", "output"):
        score.add_argument("--" + name, required=True)
    args = p.parse_args()
    if args.command == "fit":
        partitions = json.loads(Path(args.partitions).read_text(encoding="utf-8"))
        for items in partitions.values():
            for item in items:
                item["features"] = str((Path(args.partitions).resolve().parent / item["features"]).resolve())
        print(json.dumps(fit(partitions, args.output, phases=args.phase, epochs=args.epochs, device=args.device), indent=2))
    else:
        rows = read_features(args.input)
        model, meta = load_package(args.package, encoder_reference=rows[0]["encoder_reference"],
                                   context_reference=rows[0]["context_reference"])
        detector = OnlineObservationDetector(model, meta)
        with Path(args.output).open("x", encoding="utf-8") as stream:
            for row in rows:
                # Replay uses a virtual local wall clock, NOT a measured online latency.
                report = detector.detect(row, generation=0, captured_wall_s=row["sim_time_s"], now_wall_s=row["sim_time_s"])
                report.update(replay=True, wall_latency_measured=False)
                stream.write(json.dumps(report, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
