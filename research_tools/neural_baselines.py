"""Optional PyTorch CPU MLP ablations; same grouped schema, no simulator or pretrained vision."""
import argparse
import hashlib
import json
import math
import random
import subprocess
import time
from pathlib import Path
from .diagnostics import FEATURES, Ranker, require, read_rows, validate, vector


def parameters(dim, width):
    return (dim + 1) * width + (width + 1) * width + width + 1


def run(rows, seed=17, epochs=50, width=32, learning_rate=.001):
    import torch
    from torch import nn
    validate(rows)
    require(epochs > 0 and width > 0 and learning_rate > 0, "positive training configuration required")
    require(not any(r["split"] == "sealed_test" for r in rows), "sealed test forbidden")
    train = [r for r in rows if r["split"] == "train" and r["eligible"] and r["executed"]
             and r.get("autonomous_success") is not None]
    dev = [r for r in rows if r["split"] == "development" and r["eligible"]]
    require(bool(train) and bool(dev), "labeled train and development required")
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    y = torch.tensor([[float(r["autonomous_success"])] for r in train])
    target = parameters(len(vector(train[0], "B3")), width)
    summaries, predictions = {}, []
    for method in FEATURES:
        random.seed(seed)
        torch.manual_seed(seed)
        dim = len(vector(train[0], method))
        # Approximate parameter match: same depth, larger B1-only width for B4.
        hidden = (min(range(1, max(2048, width + 1)), key=lambda w: abs(parameters(dim, w) - target))
                  if method == "B4" else width)
        scale = Ranker(train, method)
        x = torch.tensor([scale.transform(vector(r, method)) for r in train], dtype=torch.float32)
        z = torch.tensor([scale.transform(vector(r, method)) for r in dev], dtype=torch.float32)
        require(bool(torch.isfinite(x).all()) and bool(torch.isfinite(z).all()), "float32 feature overflow")
        model = nn.Sequential(nn.Linear(dim, hidden), nn.ReLU(), nn.Linear(hidden, hidden),
                              nn.ReLU(), nn.Linear(hidden, 1))
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        start = time.perf_counter()
        model.train()
        for _ in range(epochs):
            optimizer.zero_grad()
            loss = nn.functional.binary_cross_entropy_with_logits(model(x), y)
            require(bool(torch.isfinite(loss)), "nonfinite training loss")
            loss.backward()
            optimizer.step()
        elapsed = time.perf_counter() - start
        model.eval()
        with torch.no_grad():
            scores = model(z).flatten().tolist()
        require(all(math.isfinite(s) for s in scores), "nonfinite prediction")
        summaries[method] = {"input_dim": dim, "hidden_width": hidden, "parameters": parameters(dim, hidden),
                             "b3_parameter_ratio": parameters(dim, hidden) / target,
                             "optimizer_steps": epochs, "train_rows": len(train), "cpu_training_seconds": elapsed,
                             "final_train_loss": float(loss.detach())}
        for r, score in zip(dev, scores):
            predictions.append({"root_id": r["root_id"], "candidate_id": r["candidate_id"],
                                "method": method, "score": score, "score_semantics": "rank_only"})
    return {"purpose": rows[0]["purpose"], "research_conclusion": "NOT_ESTABLISHED",
            "seed": seed, "epochs": epochs, "learning_rate": learning_rate, "torch_version": torch.__version__,
            "device": "cpu", "methods": summaries, "predictions": predictions,
            "warning": "Diagnostic MLPs on supplied frozen features, not paper reproductions. Equal optimizer steps do not guarantee equal FLOPs. B4 approximately matches B3 parameter count; multi-seed and closed-loop validation still required."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--width", type=int, default=32)
    args = parser.parse_args()
    require(not Path(args.output).exists(), "output already exists")
    result = run(read_rows(args.input), seed=args.seed, epochs=args.epochs, width=args.width)
    result["input_sha256"] = hashlib.sha256(Path(args.input).read_bytes()).hexdigest()
    result["code_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    result["code_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    with Path(args.output).open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)


if __name__ == "__main__":
    main()
