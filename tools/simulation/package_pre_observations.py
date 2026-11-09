"""Build a portable handoff ZIP from audited normal trials without altering raw files."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def package(batch, destination):
    batch, destination = Path(batch), Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    results = json.loads((batch / "results.json").read_text(encoding="utf-8"))
    trials, seen = [], set()
    for result in results:
        if result["status"] != "collected_verified_pending_review":
            continue
        item = result["audit"]
        if item["trial_id"] in seen:
            raise ValueError("Duplicate trial ID")
        seen.add(item["trial_id"])
        trials.append({"trial_id": item["trial_id"], "folder": f'normal-{result["index"]:02}',
                       "frames": item["rgb_shape"][0], "observations": item["observations"],
                       "dispatches": item["dispatches"], "max_gap_sim_s": item["max_rgb_gap_sim_s"],
                       "upstream_proxy": item["upstream_proxy"], "dataset_use": "unassigned",
                       "independent_review": "pending", "visual_encoder": None})
    index = {"schema": "pre-rnd-oe-handoff/1", "trials": trials,
             "method_target": "FIPER RND-OE observation branch adaptation",
             "policy": "unchanged GAM + scripted demonstration", "action_sampling_required": False,
             "normal_collection_is_detector_validation": False,
             "split_rule": "Allocate complete trial IDs; no adjacent-frame split"}
    (destination / "trial-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# RND-OE 正常观测交接包", "", "保持 GAM＋脚本控制器、固定640×480 RGB相机；无故障注入，无恢复执行。",
             "视觉编码器由马提供，拟合/校准/离线验证由胡负责。当前不含视觉embedding、RND权重或阈值。",
             "正常采集不等于A场景检测通过；所有试次用途未分配，按完整试次划分，独立审核待完成。", "",
             "| 记录 | 试次ID | RGB帧 | 观测 | 派发/反馈 |", "|---|---|---:|---:|---:|"]
    lines += [f'| {t["folder"]} | {t["trial_id"]} | {t["frames"]} | {t["observations"]} | {t["dispatches"]} |' for t in trials]
    lines += ["", "ZIP结构：每条normal-XX/raw为未改动的原始证据及逐文件SHA-256清单；export为观测索引、相机参数和样例。",
              "导出索引中的rgb_archive相对于该export文件夹；读取NPZ时使用allow_pickle=False，数组键为rgb。",
              "producer-sources保存实际采集源码；启动命令和日志位于每条normal-XX目录。",
              "操作阶段表示控制器意图，不是独立确认的正常/异常标签。只允许已发生的观测进入检测输入；最终点云和代理结果仅供独立评价。",
              "相机渲染时刻与仿真时间同域；monotonic纳秒只在本进程比较，不跨试次相减。原始最大帧间隔见trial-index.json。",
              "官方100条示范的相机/时钟兼容性尚未逐条确认，本包没有将它们混入。"]
    readme = "\n".join(lines) + "\n"
    (destination / "README.md").write_text(readme, encoding="utf-8")
    archive_path = destination / "RND-OE_正常观测交接.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("README.md", readme)
        archive.writestr("trial-index.json", json.dumps(index, indent=2, ensure_ascii=False))
        for source in (batch / "producer-sources").iterdir():
            if source.is_file():
                archive.write(source, "producer-sources/" + source.name)
        archive.write(batch / "plan.json", "plan.json")
        for trial in trials:
            folder = trial["folder"]
            root = batch / folder
            raw, = root.glob("fold-recovery-*")
            for p in raw.iterdir():
                if p.is_file():
                    archive.write(p, folder + "/raw/" + p.name)
            for p in (root / "export").iterdir():
                if p.name == "observations.jsonl":
                    records = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]
                    for row in records:
                        row["rgb_archive"] = "../raw/rgb-frames.npz"
                    archive.writestr(folder + "/export/" + p.name,
                                     "\n".join(json.dumps(r) for r in records) + "\n")
                elif p.name == "audit.json":
                    report = json.loads(p.read_text(encoding="utf-8"))
                    report["source"] = "../raw"
                    archive.writestr(folder + "/export/" + p.name, json.dumps(report, indent=2))
                else:
                    archive.write(p, folder + "/export/" + p.name)
            for name in ("console.log", "invocation.json"):
                archive.write(root / name, folder + "/" + name)
    with archive_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC check failed")
    receipt = {"file": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": digest,
               "trial_count": len(trials), "crc_checked": True}
    (destination / "package.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("batch", type=Path)
    p.add_argument("destination", type=Path)
    args = p.parse_args()
    print(json.dumps(package(args.batch, args.destination), indent=2))
