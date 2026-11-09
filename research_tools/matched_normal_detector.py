"""Fit the project detector and score three disjoint, matched normal recordings."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import torch

from .detection_encoder import export_trace, file_hash
from .garment_trace_intake import validate_trace
from .observation_detector import OnlineObservationDetector, fit, load_package, read_features
from .shared_context import content_hash

TRIALS = [
    ("normal-01", "eff5d921-804f-4aeb-b1cb-2fe6d462ee23", "fit"),
    ("normal-02", "a4d9c33f-d5e9-40d2-985d-0b06f5f3a61e", "calibration"),
    ("normal-03", "c9eb5255-24f9-451e-88c1-837a1842b73a", "development"),
]
PHASE = {f"normal-{arm}-{move}": phase for arm in ("left","right")
         for move, phase in (("lift","LIFT"),("transfer","HOLD"))}
PHASE["normal-planned-release"] = "RELEASE"
BASE = Path(__file__).resolve().parents[1]
TARGET = BASE / "docs/research/zhangmingbo/full-recovery-chain-20261108/continuation-context.json"


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf8")


def prepare(raw, weights, work, folder, uid):
    context = read(raw/"continuation-context.json")
    target = read(TARGET)
    shared = {k:context[k] for k in ("camera","controller","execution_profile","preprocessing")}
    observed = read(raw/"full-fold-recovery.json")
    trace = read(raw/"observation-trace.json")
    shared["garment"] = observed["garment"]
    if shared["garment"] != read(TARGET.parent/"full-fold-recovery.json")["garment"]:
        raise ValueError("Different garment asset")
    if (any(shared[k]!=target[k] for k in ("camera","execution_profile","preprocessing"))
            or shared["controller"]["upstream_sha256"]!=target["controller"]["upstream_sha256"]):
        raise ValueError("Target sensor/controller mismatch")
    if (any(x["trial_id"]!=uid for x in (trace,observed,context)) or
            observed["injection"] is not None or observed["recovery_enabled"] or observed.get("macro_execution")):
        raise ValueError("Unreviewed trial identity or recording condition")
    if not {"upstream-stage-1-end","upstream-stage-2-end","upstream-stage-3-end"} <= {b["phase"] for b in trace["boundaries"]}:
        raise ValueError("Incomplete folding run")
    events = [json.loads(line) for line in (raw/"pre-demo-events.jsonl").read_text("utf8").splitlines()]
    if any(e["trial_id"] != uid or e.get("sdk_result") is False for e in events):
        raise ValueError("Unexpected trial or failed recorded move")
    with np.load(raw/"rgb-frames.npz", allow_pickle=False) as data:
        validate_trace(trace,data["rgb"],position_unit_source="rad")
    cref="pre-detection-context#sha256="+content_hash(shared)
    export_trace(raw, work/folder, weights, cref)
    ids={o["observation_id"]:o for o in trace["observations"]}
    rows=read_features(work/folder/"features.jsonl")
    for row in rows:
        row["phase"]=PHASE.get(ids[row["observation_id"]]["phase"],"OTHER")
    path=work/folder/"reviewed-features.jsonl"
    with path.open("w",encoding="utf8",newline="\n") as stream:
        for row in rows: stream.write(json.dumps(row,separators=(",",":"),allow_nan=False)+"\n")
    return path, rows, shared


def run(source,weights,work):
    parts={"fit":[],"calibration":[]}
    trials={}
    summary={}
    shared=None
    for folder,uid,role in TRIALS:
        raw=source/folder/"raw"
        path,rows,context=prepare(raw,weights,work,folder,uid)
        if shared is not None and shared!=context: raise ValueError("Mixed normal capture configurations")
        shared=context
        trials[uid]=rows
        item={"features":path.relative_to(work).as_posix(),"feature_sha256":file_hash(path),
              "source_reference":"manifest#sha256="+file_hash(raw/"manifest.json"),"normal_review":True,
              "review_reference":"docs/design/matched-normal-detector.md#normal-review"}
        if role in parts: parts[role].append(item)
        summary[uid]={"folder":folder,"role":role,"frames":len(rows),"feature_sha256":item["feature_sha256"],
                      "source_reference":item["source_reference"],"phases":dict(Counter(r["phase"] for r in rows))}
    save(work/"partitions.json",parts)
    save(work/"sensor-context.json",shared)
    # Relative paths keep the package reproducible and portable.
    cwd=Path.cwd()
    try:
        os.chdir(work)
        meta=fit(parts,"package",phases=["LIFT","HOLD"])
    finally:
        os.chdir(cwd)
    model,checked=load_package(work/"package",encoder_reference=meta["encoder_reference"],context_reference=meta["context_reference"])
    for folder,uid,role in TRIALS:
        detector=OnlineObservationDetector(model,checked)
        counts=Counter()
        with (work/(folder+"-scores.jsonl")).open("w",encoding="utf8",newline="\n") as stream:
            for row in trials[uid]:
                report=detector.detect(row,generation=0,captured_wall_s=row["sim_time_s"],now_wall_s=row["sim_time_s"])
                report.update(replay=True,wall_latency_measured=False,controller_phase=row["phase"])
                stream.write(json.dumps(report,allow_nan=False,separators=(",",":"))+"\n")
                counts[(report["status"],report["reason"])]+=1
        summary[uid]["reports"]={status+"/"+reason:n for (status,reason),n in counts.items()}
    save(work/"review.json",summary)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ("source","weights","output"): parser.add_argument("--"+arg,required=True,type=Path)
    args=parser.parse_args()
    torch.set_num_threads(2)
    dest=args.output.resolve()
    if dest.exists():parser.error("choose a new output directory")
    dest.parent.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(dir=dest.parent) as temp:
        work=Path(temp)/"result";work.mkdir()
        run(args.source.resolve(),args.weights.resolve(),work)
        work.rename(dest)
