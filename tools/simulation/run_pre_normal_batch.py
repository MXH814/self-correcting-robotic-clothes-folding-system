"""Collect three independent normal trials for whole-trial RND-OE data allocation."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def main(output, count=3):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "producer-sources"
    sources.mkdir()
    for p in Path(__file__).parent.iterdir():
        if p.suffix in (".py", ".ps1"):
            shutil.copyfile(p, sources / p.name)
    plan = {"schema": "pre-normal-batch/1", "trials": count, "automatic_retries": 0,
            "controller": "GAM + original script", "fault_injection": False,
            "recovery_enabled": False, "encoder": None, "detector_status": "UNKNOWN",
            "allocation": "unassigned whole trials; Hu determines fit/calibration/development",
            "synthetic_data": False, "simulator_seed": None}
    (output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    results = []
    for index in range(1, count + 1):
        root = output / f"normal-{index:02}"
        root.mkdir()
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(sources / "run_local.ps1"), "-Stage", "fold-recovery", "-Headless", "-OutputRoot", str(root)]
        env = dict(os.environ, ROBOTICS_PRE_NORMAL_COLLECTION="1")
        env.pop("ROBOTICS_FIPER_PRE_SCENARIO", None)
        (root / "invocation.json").write_text(json.dumps({"argv": command,
            "ROBOTICS_PRE_NORMAL_COLLECTION": "1"}, indent=2), encoding="utf-8")
        print("START_NORMAL", index, flush=True)
        start = time.monotonic()
        memory_issue = False
        log_path = root / "console.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
            while process.poll() is None:
                time.sleep(5)
                content = log_path.read_text(encoding="utf-8", errors="replace")
                if re.search(r"CUDA out of memory|MemoryError|bad_alloc|failed to allocate.*(?:memory|bytes)|out of host memory", content, re.I):
                    if not memory_issue:
                        print("MEMORY_BLOCKED", index, "inspect", str(log_path), flush=True)
                    memory_issue = True
        trials = list(root.glob("fold-recovery-*"))
        result = {"index": index, "exit_code": process.returncode, "wall_s": time.monotonic() - start,
                  "memory_error_reported": memory_issue, "status": "incomplete"}
        if process.returncode == 0 and len(trials) == 1:
            from verify_pre_observations import audit
            try:
                result["audit"] = audit(trials[0], root / "export")
                result["status"] = "collected_verified_pending_review"
            except Exception as error:
                result["status"] = "audit_failed"
                result["error"] = repr(error)
        results.append(result)
        (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print("END_NORMAL", index, result["status"], flush=True)
        if memory_issue or result["status"] != "collected_verified_pending_review":
            print("BATCH_STOPPED_NO_RETRY", flush=True)
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--count", type=int, choices=range(1, 4), default=3)
    args = parser.parse_args()
    main(args.output, args.count)
