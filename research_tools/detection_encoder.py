"""Frozen ImageNet ResNet18 observation adapter; not a VLA/policy embedding.

No torchvision binary extension is needed inside Isaac's Python. The attributed
ResNet implementation and official weights are loaded strictly; inference never
downloads a model or silently falls back to random weights.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

import numpy as np

from .diagnostics import require

WEIGHTS_URL = "https://download.pytorch.org/models/resnet18-f37072fd.pth"
WEIGHTS_PREFIX = "f37072fd"
WEIGHTS_SHA256 = "f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec"
ENCODER_VERSION = "resnet18-imagenet1k-v1-pil-resize256-centercrop224/1"


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fetch_weights(destination):
    """Explicit preparation command, never called by online inference."""
    destination = Path(destination)
    require(not destination.exists(), "weights destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    with urllib.request.urlopen(WEIGHTS_URL, timeout=30) as source, partial.open("xb") as target:
        while block := source.read(1024 * 1024):
            target.write(block)
    require(file_hash(partial) == WEIGHTS_SHA256, "official weights hash mismatch")
    partial.rename(destination)
    return {"url": WEIGHTS_URL, "sha256": file_hash(destination)}


def preprocess(rgb):
    """PIL bilinear short-edge resize and center crop, then ImageNet normalization."""
    import torch
    from PIL import Image
    require(isinstance(rgb, np.ndarray) and rgb.dtype == np.uint8 and rgb.ndim == 3
            and rgb.shape[2] == 3 and min(rgb.shape[:2]) > 0, "expected uint8 HWC RGB")
    image = Image.fromarray(rgb)
    w, h = image.size
    size = (int(256 * w / h), 256) if h <= w else (256, int(256 * h / w))
    image = image.resize(size, Image.Resampling.BILINEAR)
    left, top = round((size[0] - 224) / 2), round((size[1] - 224) / 2)
    image = image.crop((left, top, left + 224, top + 224))
    x = torch.from_numpy(np.array(image, copy=True)).permute(2, 0, 1).float() / 255
    return (x - torch.tensor([.485, .456, .406])[:, None, None]) / torch.tensor([.229, .224, .225])[:, None, None]


class FrozenRGBEncoder:
    def __init__(self, weights, device="cpu"):
        import torch
        from third_party.torchvision.resnet import BasicBlock, ResNet
        weights = Path(weights)
        require(weights.is_file(), "missing pretrained encoder weights")
        sha = file_hash(weights)
        require(sha == WEIGHTS_SHA256, "unrecognized pretrained encoder weights")
        self.device = torch.device(device)
        self.model = ResNet(BasicBlock, [2, 2, 2, 2])
        self.model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
        self.model.fc = torch.nn.Identity()
        self.model.requires_grad_(False).eval().to(self.device)
        self.reference = ENCODER_VERSION + "#sha256=" + sha

    def encode(self, images):
        import torch
        require(len(images) > 0, "empty image batch")
        with torch.inference_mode():
            result = self.model(torch.stack([preprocess(x) for x in images]).to(self.device))
        require(result.shape == (len(images), 512) and bool(torch.isfinite(result).all()), "invalid embedding")
        return result.cpu().numpy()


def export_trace(directory, output, weights, context_reference, phase="UNSPECIFIED", batch_size=8):
    """Export ONLY RGB embeddings. No condition, injection, mesh or outcome input.

    UNSPECIFIED is deliberate: a controller phase must be supplied/verified before
    fitting or online use. This command does not infer failure labels or splits.
    """
    from .garment_trace_intake import verify_files
    directory, output = Path(directory).resolve(), Path(output).resolve()
    require(directory != output and directory not in output.parents, "output must be outside original evidence")
    require(not output.exists(), "output already exists")
    require(isinstance(context_reference, str) and bool(context_reference), "sensor context required")
    require(type(batch_size) is int and batch_size > 0, "invalid batch size")
    source_manifest = verify_files(directory)
    trace = json.loads((directory / "observation-trace.json").read_text(encoding="utf-8"))
    require(trace.get("schema") == "garment-observation-trace-v1"
            and source_manifest["trial_id"] == trace["trial_id"], "invalid/cross-trial trace")
    require(trace["frame_archive"]["file"] == "rgb-frames.npz"
            and file_hash(directory / "rgb-frames.npz") == trace["frame_archive"]["sha256"], "RGB binding")
    with np.load(directory / "rgb-frames.npz", allow_pickle=False) as archive:
        frames = archive["rgb"]
    require(frames.dtype == np.uint8 and frames.ndim == 4 and frames.shape[-1] == 3
            and len(frames) > 0 and list(frames.shape) == trace["frame_archive"]["shape"], "invalid RGB archive")
    encoder = FrozenRGBEncoder(weights)
    embeddings = np.concatenate([encoder.encode(frames[i:i + batch_size])
                                 for i in range(0, len(frames), batch_size)])
    rows, seen = [], set()
    for obs in trace["observations"]:
        key = (obs["rendering_frame"], obs["rendering_time_s"])
        if key in seen:
            continue
        seen.add(key)
        rows.append({"trial_id": trace["trial_id"], "lineage_group": trace["trial_id"],
                     "observation_id": obs["observation_id"], "frame_id": str(obs["rendering_frame"]),
                     "sim_time_s": obs["rendering_time_s"], "phase": phase,
                     "read_sim_time_s": obs["camera_read_end"]["sim_time_s"],
                     "context_reference": context_reference, "encoder_reference": encoder.reference,
                     "embedding": embeddings[obs["frame_index"]].tolist()})
    output.mkdir(parents=True)
    with (output / "features.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    meta = {"schema": "detection-feature-export/1", "trial_id": trace["trial_id"], "frames": len(rows),
            "encoder_reference": encoder.reference, "context_reference": context_reference,
            "phase": phase, "source_trace_sha256": file_hash(directory / "observation-trace.json"),
            "feature_sha256": file_hash(output / "features.jsonl"), "input": "RGB only",
            "normal_review": None, "split": "unassigned", "online_verified": False}
    (output / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    download = sub.add_parser("fetch-weights")
    download.add_argument("--output", required=True)
    encode = sub.add_parser("encode-trace")
    for name in ("input", "output", "weights", "context-reference"):
        encode.add_argument("--" + name, required=True)
    encode.add_argument("--phase", default="UNSPECIFIED")
    encode.add_argument("--batch-size", type=int, default=8)
    args = p.parse_args()
    if args.command == "fetch-weights":
        result = fetch_weights(args.output)
    else:
        result = export_trace(args.input, args.output, args.weights, args.context_reference,
                              args.phase, args.batch_size)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
