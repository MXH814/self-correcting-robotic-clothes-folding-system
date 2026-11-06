"""Python 3.9+ standard-library diagnostic runner. See docs/research/execution-guide.md."""
import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

FEATURES = {
    "B0": ("current",),
    "B1": ("current", "stage_budget"),
    "B2": ("current", "stage_budget", "visual_history"),
    "B3": ("current", "stage_budget", "visual_history", "action_history"),
    # Higher-flexibility current-only control, not a parameter-matched neural model.
    "B4": ("current", "stage_budget"),
}


class DataError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DataError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def forward_stage_score(failure_distance, recovery_distance):
    """Planning proxy inspired by AgentChord, not physical quality or probability."""
    require(finite(failure_distance) and finite(recovery_distance)
            and failure_distance >= 0 and recovery_distance >= 0, "invalid graph distance")
    return -recovery_distance if recovery_distance <= failure_distance else None


def validate(rows):
    """Strict complete-pool schema. Unexecuted/unknown outcomes stay null."""
    require(bool(rows), "empty dataset")
    keys, dimensions, groups, lineage = set(), {}, defaultdict(list), {}
    for r in rows:
        for field in ("root_id", "family_id", "garment_id", "candidate_id", "split",
                      "purpose", "controller_version", "candidate_pool_version", "feature_version"):
            require(isinstance(r.get(field), str) and bool(r[field]), "missing/string: " + field)
        require(r["split"] in ("train", "validation", "development", "sealed_test"), "invalid split")
        require(r["purpose"] in ("research", "synthetic"), "invalid purpose")
        key = (r["root_id"], r["candidate_id"])
        require(key not in keys, "duplicate candidate: " + str(key))
        keys.add(key)
        for field in ("garment_id", "root_id", "family_id"):
            k = (field, r[field])
            require(k not in lineage or lineage[k] == r["split"], "cross-split leakage: " + str(k))
            lineage[k] = r["split"]
        require(type(r.get("executed")) is bool, "executed must be bool")
        require(type(r.get("eligible")) is bool, "eligible must be bool")
        for field in ("local_success", "autonomous_success"):
            require(r.get(field) is None or type(r[field]) is bool, "label must be bool/null: " + field)
            require(r["executed"] or r.get(field) is None, "unexecuted candidate has outcome")
        if r.get("autonomous_success") is True:
            require(r.get("runtime_completed") is True and r.get("offline_quality") is True
                    and r.get("help_requested") is False and r.get("assisted") is False,
                    "success requires completion + quality + no help/assistance")
        require(finite(r.get("local_score")), "finite local_score required")
        if "stage_cost_score" in r:
            require(finite(r["stage_cost_score"]), "finite stage_cost_score required")
        f = r.get("features", {})
        require(set(f) == {"current", "stage_budget", "visual_history", "action_history"},
                "unexpected feature blocks (hidden/future inputs forbidden)")
        provenance = r.get("feature_provenance", {})
        require(set(provenance) == set(f), "provenance must cover all blocks")
        for name, vector in f.items():
            require(isinstance(vector, list) and len(vector) > 0 and all(finite(x) for x in vector),
                    "invalid feature vector: " + name)
            require(name not in dimensions or dimensions[name] == len(vector), "dimension mismatch")
            dimensions[name] = len(vector)
            p = provenance[name]
            require(p.get("source") in ("camera", "proprio", "executed_history", "task_context"),
                    "non-online provenance")
            require(p.get("uses_future") is False and p.get("privileged") is False,
                    "future/privileged feature")
            require(finite(p.get("latest_sim_s")) and finite(r.get("decision_sim_s"))
                    and p["latest_sim_s"] <= r["decision_sim_s"], "feature after decision")
        groups[r["root_id"]].append(r)
    for root, pool in groups.items():
        require(len(pool) <= 8, "candidate pool exceeds 8: " + root)
        for field in ("family_id", "garment_id", "split", "purpose", "controller_version",
                      "candidate_pool_version", "feature_version", "decision_sim_s"):
            require(len({x[field] for x in pool}) == 1, "inconsistent root field: " + field)
    require(len({r["purpose"] for r in rows}) == 1, "cannot mix synthetic and research")
    require(len({r["controller_version"] for r in rows}) == 1, "mixed continuation controllers")
    require(len({r["feature_version"] for r in rows}) == 1, "mixed feature definitions")
    require(all("stage_cost_score" in r for r in rows) or all("stage_cost_score" not in r for r in rows),
            "stage cost scores must cover entire dataset or be absent")
    return rows


def read_rows(path):
    with Path(path).open(encoding="utf-8") as f:
        return validate([json.loads(line) for line in f if line.strip()])


def grouped_split(rows, seed=17):
    """Connected components keep ANY shared garment, root or family together."""
    require(not any(r.get("split") == "sealed_test" for r in rows), "cannot repartition sealed test")
    # Validate shape/labels while temporarily ignoring existing split assignments.
    validate([dict(r, split="development") for r in rows])
    parents = list(range(len(rows)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    seen = {}
    for i, r in enumerate(rows):
        for field in ("garment_id", "root_id", "family_id"):
            key = (field, r[field])
            if key in seen:
                parents[find(i)] = find(seen[key])
            seen[key] = i
    components = defaultdict(list)
    for i in range(len(rows)):
        components[find(i)].append(i)
    blocks = sorted(components.values(), key=lambda block: min(rows[i]["root_id"] for i in block))
    require(len(blocks) >= 3, "need >=3 independent garment/lineage components")
    random.Random(seed).shuffle(blocks)
    ntrain = min(len(blocks) - 2, max(1, int(.6 * len(blocks))))
    nval = min(len(blocks) - ntrain - 1, max(1, int(.2 * len(blocks))))
    output = [dict(r) for r in rows]
    for j, block in enumerate(blocks):
        split = "train" if j < ntrain else "validation" if j < ntrain + nval else "development"
        for i in block:
            output[i]["split"] = split
    return validate(output)


def vector(row, method):
    return [x for block in FEATURES[method] for x in row["features"][block]]


class Ranker:
    """Train-only standardized kNN; outputs rank scores, NOT calibrated probabilities."""
    def __init__(self, train, method):
        self.method = method
        self.train = [r for r in train if r["eligible"] and r["executed"]
                      and r.get("autonomous_success") is not None]
        require(bool(self.train), "no eligible labeled training candidates")
        require(all(r["split"] == "train" for r in self.train), "fit accepts train only")
        raw = [vector(r, method) for r in self.train]
        self.mean = [sum(col) / len(col) for col in zip(*raw)]
        self.scale = [math.sqrt(sum((x - mu) ** 2 for x in col) / len(col)) or 1.
                      for col, mu in zip(zip(*raw), self.mean)]
        self.x = [self.transform(v) for v in raw]
        self.k = 1 if method == "B4" else min(5, len(self.train))

    def transform(self, raw):
        return [(x - m) / s for x, m, s in zip(raw, self.mean, self.scale)]

    def score(self, row):
        x = self.transform(vector(row, self.method))
        neighbors = sorted(range(len(self.x)), key=lambda i: (
            sum((a - b) ** 2 for a, b in zip(x, self.x[i])),
            self.train[i]["root_id"], self.train[i]["candidate_id"]))[:self.k]
        return sum(self.train[i]["autonomous_success"] for i in neighbors) / len(neighbors)


def wilson(successes, n):
    if n == 0:
        return None
    z, p = 1.959963984540054, successes / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0., center - half), min(1., center + half)]


def paired_bootstrap(pairs, seed=17, repetitions=2000):
    """Garment-cluster bootstrap; pairs=(garment, method_success - reference_success)."""
    grouped = defaultdict(list)
    for garment, delta in pairs:
        grouped[garment].append(delta)
    keys = sorted(grouped)
    if len(keys) < 2:
        return None
    rng, samples = random.Random(seed), []
    for _ in range(repetitions):
        values = [v for k in rng.choices(keys, k=len(keys)) for v in grouped[k]]
        samples.append(sum(values) / len(values))
    samples.sort()
    return [samples[int(.025 * repetitions)], samples[min(repetitions - 1, int(.975 * repetitions))]]


def evaluate(rows, seed=17, external_predictions=None):
    validate(rows)
    require(not any(r["split"] == "sealed_test" for r in rows), "sealed test forbidden in development runner")
    train = [r for r in rows if r["split"] == "train"]
    dev = [r for r in rows if r["split"] == "development"]
    require(bool(train) and bool(dev), "need train and development splits")
    models = {m: Ranker(train, m) for m in FEATURES}
    groups = defaultdict(list)
    for r in dev:
        groups[r["root_id"]].append(r)
    external = {}
    if external_predictions is not None:
        expected = {(r["root_id"], r["candidate_id"], m) for r in dev if r["eligible"] for m in FEATURES}
        for p in external_predictions:
            key = (p.get("root_id"), p.get("candidate_id"), p.get("method"))
            require(key in expected and key not in external and finite(p.get("score"))
                    and p.get("score_semantics") == "rank_only", "invalid/duplicate external prediction")
            external[key] = p["score"]
        require(set(external) == expected, "external predictions must cover identical eligible pools and B0-B4")
    selections, pool_summary, cross = [], [], Counter()
    for root, pool in sorted(groups.items()):
        eligible = sorted((r for r in pool if r["eligible"]), key=lambda r: r["candidate_id"])
        complete = bool(eligible) and all(r["executed"] and r.get("autonomous_success") is not None for r in eligible)
        oracle = any(r.get("autonomous_success") is True for r in eligible)
        pool_summary.append({"root_id": root, "eligible_candidates": len(eligible),
                             "fully_evaluated": complete, "known_success_exists": oracle})
        for r in pool:
            if r["eligible"]:
                cross[str(r.get("local_success")) + "/" + str(r.get("autonomous_success"))] += 1
        if not eligible:
            continue
        rng = random.Random(str(seed) + ":" + root)
        choices = {"fixed": eligible[0], "random": rng.choice(eligible),
                   "local": max(eligible, key=lambda r: (r["local_score"], -eligible.index(r)))}
        if "stage_cost_score" in eligible[0]:
            choices["stage_cost"] = max(eligible, key=lambda r: r["stage_cost_score"])
        scores = {}
        for method, model in models.items():
            scores[method] = {r["candidate_id"]: (external[(root, r["candidate_id"], method)]
                              if external_predictions is not None else model.score(r)) for r in eligible}
            choices[method] = max(eligible, key=lambda r: scores[method][r["candidate_id"]])
        for method, choice in choices.items():
            selections.append({"root_id": root, "garment_id": choice["garment_id"], "method": method,
                               "candidate_id": choice["candidate_id"], "complete_pool": complete,
                               "oracle_success": oracle, "success": choice.get("autonomous_success"),
                               "score": scores.get(method, {}).get(choice["candidate_id"]),
                               "score_semantics": "rank_only"})
    summary = {}
    methods = list(FEATURES) + ["fixed", "random", "local"]
    if "stage_cost_score" in rows[0]:
        methods.append("stage_cost")
    for method in methods:
        selected = [s for s in selections if s["method"] == method]
        complete = [s for s in selected if s["complete_pool"]]
        n, wins = len(complete), sum(s["success"] is True for s in complete)
        conditional = [s for s in complete if s["oracle_success"]]
        summary[method] = {"all_roots": len(groups), "selected_roots": len(selected),
                           "paired_complete_roots": n, "successes": wins,
                           "observed_successes_over_all_roots": wins / len(groups),
                           "complete_pool_success_rate": wins / n if n else None,
                           "wilson95_complete_pool_descriptive": wilson(wins, n),
                           "oracle_available_roots": len(conditional),
                           "conditional_selection_rate": (sum(s["success"] is True for s in conditional)
                                                          / len(conditional)) if conditional else None}
    reference = {s["root_id"]: s for s in selections if s["method"] == "B1" and s["complete_pool"]}
    comparisons = {}
    for method in [m for m in methods if m not in ("B1", "fixed", "random")]:
        pairs = [(s["garment_id"], int(s["success"]) - int(reference[s["root_id"]]["success"]))
                 for s in selections if s["method"] == method and s["complete_pool"]
                 and s["root_id"] in reference]
        comparisons[method + "_vs_B1"] = {"n": len(pairs),
            "win_tie_loss": dict(Counter("win" if d > 0 else "loss" if d < 0 else "tie" for _, d in pairs)),
            "delta": sum(d for _, d in pairs) / len(pairs) if pairs else None,
            "garment_bootstrap95": paired_bootstrap(pairs, seed)}
    return {"purpose": rows[0]["purpose"], "research_conclusion": "NOT_ESTABLISHED",
            "ranking_backend": "external_rank_scores" if external_predictions is not None else "knn",
            "warning": "Offline candidate replay only; no closed-loop robot result. Default B4 is 1NN; external score provenance must be checked. Wilson intervals ignore clustering; use cluster bootstrap for paired effects.",
            "seed": seed, "pools": pool_summary, "summary": summary, "paired": comparisons,
            "h2_local_final_branch_counts": dict(cross), "selections": selections}


def calibration_metrics(records):
    """Held-out VALIDATION diagnostics, not a calibration fit or dispatch certificate."""
    require(bool(records), "no calibration records")
    seen = set()
    for r in records:
        require(r.get("split") == "validation", "calibration diagnostic accepts validation only")
        require(finite(r.get("probability")) and 0 <= r["probability"] <= 1, "bad probability")
        require(type(r.get("success")) is bool, "bad success label")
        require(r.get("calibrator_fit_disjoint") is True, "must attest disjoint calibrator fit data")
        key = (r.get("root_id"), r.get("candidate_id"))
        require(all(isinstance(x, str) and x for x in key) and key not in seen, "bad/duplicate calibration key")
        seen.add(key)
    bins = []
    for i in range(10):
        group = [r for r in records if min(9, int(r["probability"] * 10)) == i]
        bins.append({"bin": i, "n": len(group),
                     "mean_probability": sum(r["probability"] for r in group) / len(group) if group else None,
                     "success_rate": sum(r["success"] for r in group) / len(group) if group else None})
    return {"n": len(records), "brier": sum((r["probability"] - r["success"]) ** 2 for r in records) / len(records),
            "ece10": sum(b["n"] * abs(b["mean_probability"] - b["success_rate"]) for b in bins if b["n"]) / len(records),
            "bins": bins, "dispatch_authorized": False}


def synthetic():
    """Deterministic manufactured fixture, never evidence for H1/H2."""
    rows = []
    for i in range(18):
        for c in range(2):
            rows.append({"root_id": "synthetic-root-%02d" % i, "family_id": "synthetic-family-%02d" % i,
                         "garment_id": "synthetic-garment-%02d" % i, "candidate_id": str(c),
                         "split": "development", "purpose": "synthetic", "controller_version": "fixture",
                         "candidate_pool_version": "fixture", "feature_version": "fixture", "decision_sim_s": 2.,
                         "eligible": True, "executed": True, "local_score": float(c), "local_success": bool(c),
                         "autonomous_success": c == i % 2, "runtime_completed": c == i % 2,
                         "offline_quality": c == i % 2, "help_requested": False, "assisted": False,
                         "features": {"current": [float(c)], "stage_budget": [0., 1.],
                                      "visual_history": [float(i % 2)], "action_history": [float(c), float(i % 2)]},
                         "feature_provenance": {name: {"source": "executed_history" if "history" in name else "camera",
                                                       "uses_future": False, "privileged": False, "latest_sim_s": 1.}
                                                for name in ("current", "stage_budget", "visual_history", "action_history")}})
    return grouped_split(rows)


def write_jsonl(path, rows):
    with Path(path).open("x", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fixture", "validate", "split", "evaluate", "calibration"))
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--predictions", help="optional neural_baselines JSON output for evaluate")
    args = parser.parse_args()
    if args.command != "fixture" and not args.input:
        parser.error("--input required")
    if args.command in ("fixture", "split"):
        if not args.output:
            parser.error("--output required")
        raw = ([json.loads(x) for x in Path(args.input).read_text(encoding="utf-8").splitlines() if x.strip()]
               if args.input else None)
        write_jsonl(args.output, synthetic() if raw is None else grouped_split(raw, args.seed))
        return
    if args.command == "calibration":
        records = [json.loads(x) for x in Path(args.input).read_text(encoding="utf-8").splitlines() if x.strip()]
        result = calibration_metrics(records)
    else:
        rows = read_rows(args.input)
        external = None
        if args.predictions:
            require(args.command == "evaluate", "--predictions applies only to evaluate")
            payload = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
            require(payload.get("input_sha256") == hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
                    "predictions input hash mismatch")
            require(payload.get("purpose") == rows[0]["purpose"], "prediction purpose mismatch")
            external = payload["predictions"]
        result = {"rows": len(rows), "valid": True} if args.command == "validate" else evaluate(rows, args.seed, external)
        if args.predictions:
            result["predictions_sha256"] = hashlib.sha256(Path(args.predictions).read_bytes()).hexdigest()
    result["input_sha256"] = hashlib.sha256(Path(args.input).read_bytes()).hexdigest()
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        Path(args.output).open("x", encoding="utf-8").write(content + "\n")
    else:
        print(content)


if __name__ == "__main__":
    main()
