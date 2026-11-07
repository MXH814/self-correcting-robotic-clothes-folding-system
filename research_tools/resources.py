"""Measured-input resource estimator. No cloud access, allocation or purchase."""
import argparse
import json
import math


def estimate(roots, candidates, repetitions, rollout_seconds, training_gpu_hours,
             hourly_price, bytes_per_rollout, overhead_fraction=0.2):
    values = (roots, candidates, repetitions, rollout_seconds, training_gpu_hours,
              hourly_price, bytes_per_rollout, overhead_fraction)
    if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("inputs must be finite and nonnegative")
    if any(type(x) is not int or x < 1 for x in (roots, candidates, repetitions)) or candidates > 8:
        raise ValueError("positive integer roots/repetitions; candidates 1..8")
    if rollout_seconds <= 0:
        raise ValueError("measured rollout_seconds must be positive")
    branches = roots * candidates * repetitions
    evaluation_hours = branches * rollout_seconds / 3600
    billed_hours = (evaluation_hours + training_gpu_hours) * (1 + overhead_fraction)
    return {"status": "ESTIMATE_NOT_BILL", "branch_rollouts": branches,
            "sequential_evaluation_hours": evaluation_hours, "estimated_billed_hours": billed_hours,
            "estimated_cost_same_currency_as_input": billed_hours * hourly_price,
            "estimated_bytes": branches * bytes_per_rollout,
            "assumptions": "Single sequential billed device; same hourly price for training/evaluation; overhead applied to both. No measured throughput or cloud quote is supplied by this tool."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON with explicit measured/estimated estimator inputs")
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as f:
        print(json.dumps(estimate(**json.load(f)), indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
