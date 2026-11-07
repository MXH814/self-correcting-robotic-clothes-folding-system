"""Audit the submitted handoff files without loading the unavailable raw NPZ."""
import argparse
import json
from pathlib import Path, PurePosixPath
from .diagnostics import finite, require
from .legacy_observations import digest


def audit(repo):
    repo = Path(repo).resolve()
    directory = repo / "docs/research/zhangmingbo"
    manifest = json.loads((directory / "artifact-manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest["artifacts"]
    require(len({a["id"] for a in artifacts}) == len(artifacts), "duplicate artifact IDs")
    verified = []
    for artifact in artifacts:
        if "repo_path" not in artifact:
            continue
        path = repo.joinpath(*PurePosixPath(artifact["repo_path"]).parts).resolve()
        require(repo in path.parents, "artifact path outside repository")
        require(path.is_file(), "missing repository artifact")
        require(path.stat().st_size == artifact["size_bytes"] and digest(path) == artifact["sha256"],
                "artifact size/hash mismatch: " + artifact["id"])
        verified.append(artifact["id"])
    sample = json.loads((directory / "observation-example.json").read_text(encoding="utf-8"))
    trajectory = next(a for a in artifacts if a["id"] == "gui-demo-trajectory-2")
    require(sample["source_sha256"] == trajectory["sha256"], "sample/trajectory declared lineage mismatch")
    joints = sample["joint_state"]
    require(len(joints) == 60 and all(finite(v) for v in joints)
            and sample["fields"]["joint_state"]["shape"] == [60], "invalid submitted joint sample")
    require(sample.get("action") is None and sample.get("timestamps") == "not recorded",
            "legacy sample unexpectedly asserts action/time")
    return {"schema_version": "handoff-audit/1", "verified_repo_artifacts": verified,
            "input_sha256": {"artifact_manifest": digest(directory / "artifact-manifest.json"),
                             "observation_example": digest(directory / "observation-example.json")},
            "evidence_scope": "Repository bytes and sample schema; lineage and image timing are submission declarations, not independent NPZ extraction.",
            "submitted_observation": {"stage": sample["stage"], "index": sample["index"],
                                      "joint_values": len(joints), "all_finite": True,
                                      "raw_min": min(joints), "raw_max": max(joints)},
            "raw_npz_independently_verified": False, "image_is_same_observation_frame": False,
            "online_authorized": False, "h1_h2_evidence": False,
            "remaining": ["accessible original trajectory and run environment",
                          "joint name/index/type/unit mapping", "matched camera frame and provenance",
                          "real timestamps and executed action acknowledgments",
                          "failure branches and independently reviewed outcomes"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output")
    args = parser.parse_args()
    result = audit(args.repo_root)
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        with Path(args.output).open("x", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
