"""Independent raw-output/selection/integrity checks for the completed sweep."""
from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "src"), str(BASE), str(ROOT)]
from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock
from geosolver.problem.models import ExactAnswer
from pydantic import TypeAdapter


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def main():
    manifest = json.loads((BASE / "manifest.json").read_text())
    issues = []
    assert source_tree_hash() == manifest["source_hash"] and verify_engine_lock()[0]
    assert not subprocess.check_output(["git", "diff", manifest["frozen_commit"], "--", "src"], cwd=ROOT)
    for pop in manifest["populations"]:
        data = (ROOT / pop["path"]).read_bytes()
        assert sha(data) == pop["sha256"]
        corpus = [json.loads(l) for l in data.splitlines() if l.strip()]
        expected = sorted(corpus, key=lambda r: (sha(f"{manifest['selection_seed']}:{pop['group']}:{r['id']}".encode()), r["id"]))[:10]
        chosen = sorted([c for c in manifest["cases"] if c["group"] == pop["group"]], key=lambda c: c["rank"])
        assert [r["id"] for r in expected] == [r["id"] for r in chosen]
        for row, case in zip(expected, chosen):
            dsl = (ROOT / case["dsl_path"]).read_bytes()
            assert sha(dsl) == case["dsl_sha256"] and json.loads(dsl) == row["dsl"]
    raw = Path(manifest["raw_root"])
    observed, statuses, total_raw_bytes, total_gzip_bytes = [], Counter(), 0, 0
    expected_import = str(ROOT / "src/geosolver")
    expected_dependencies = manifest["runtime_fingerprint"]["runtime_dependencies"]
    adapter = TypeAdapter(ExactAnswer)
    for job in manifest["jobs"]:
        path = BASE / "receipts" / f"{job['job']}.json"
        assert path.exists(), job
        receipt = json.loads(path.read_text())
        assert all(receipt[k] == v for k, v in job.items())
        assert receipt["manifest_sha256"] == sha((BASE / "manifest.json").read_bytes())
        compressed = raw / "outputs" / f"{job['job']}.json.gz"
        result = {}
        if compressed.exists():
            zipped = compressed.read_bytes()
            data = gzip.decompress(zipped)
            assert sha(zipped) == receipt["gzip_sha256"]
            assert sha(data) == receipt["raw_sha256"] and len(data) == receipt["raw_bytes"]
            total_raw_bytes += len(data)
            total_gzip_bytes += len(zipped)
            result = json.loads(data)
            assert result["engine"]["source_hash"] == manifest["source_hash"]
            assert result["requested_resources"] == {"cores": job["cores"], "seed": job["seed"], "time_limit_seconds": float(job["budget"])}
            assert result["used_resources"] == {"cores": 1, "seed": job["seed"], "time_limit_seconds": float(job["budget"])}
        keys = sorted({canonical(adapter.validate_python(a).canonical_key()) for a in result.get("answers", [])})
        assert keys == receipt["answer_keys"]
        case = manifest["cases"][job["case_index"]]
        info = (result.get("diagnostics") or {}).get("process_info", {})
        if result.get("status") in ("solved", "no_answer_found"):
            assert info["import_root"] == expected_import and info["cpu_affinity"] == [receipt["cpu"]]
            assert info["effective_cores"] == 1
            for name, version in expected_dependencies.items():
                if name != "geosolver":
                    assert info["installed_dependencies"][name] == version, (job, name)
        correct = (result.get("status") in ("solved", "no_answer_found") and keys == case["expected_keys"]
                   and not receipt["outer_timeout"] and not receipt["parse_error"] and not receipt["contract_issues"])
        assert bool(correct) == receipt["matched"]
        if receipt["normal"]:
            assert receipt["returncode"] == 0
        observed.append(receipt)
        statuses[receipt["status"]] += 1
    assert len(observed) == len(manifest["jobs"]) == 216
    assert len(list((BASE / "receipts").glob("*.json"))) == 216
    assert len(list((raw / "starts").glob("*.json"))) == 216
    end = json.loads((BASE / "execution-end.json").read_text())
    assert end["completed"] == end["scheduled"] == 216 and not end["errors"]
    intervals = []
    for r in observed:
        intervals.extend([(r["started_utc"], 1), (r["finished_utc"], -1)])
    active, maximum = 0, 0
    for _, change in sorted(intervals, key=lambda p: (p[0], p[1])):
        active += change
        maximum = max(maximum, active)
    assert maximum <= 3 and active == 0
    sizes = [(str(p.relative_to(BASE)), p.stat().st_size) for p in BASE.rglob("*") if p.is_file()]
    assert all(size <= 5_000_000 for _, size in sizes)
    audit = {"ok": True, "scheduled": 216, "observed": 216, "correct": sum(r["matched"] for r in observed),
             "failures_kept_in_denominator": sum(not r["matched"] for r in observed), "status_counts": dict(statuses),
             "source_hash": source_tree_hash(), "src_diff_from_frozen": "empty", "input_selection_recomputed": True,
             "raw_bytes_rehashed": total_raw_bytes, "gzip_bytes_rehashed": total_gzip_bytes,
             "worker_identity_dependencies_affinity_checked": True, "peak_overlapping_receipts": maximum,
             "largest_repository_file": max(sizes, key=lambda pair: pair[1]), "issues": issues}
    (BASE / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
