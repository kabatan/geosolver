"""Prepare and hash everything before the first registered solve."""
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
SOURCE = Path("/tmp/switch-impl")
EXPECTED = "sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(root, revision, paths, dest):
    content = subprocess.check_output(["git", "-C", str(root), "archive", revision, *paths])
    with tarfile.open(fileobj=io.BytesIO(content)) as tar:
        tar.extractall(dest, filter="data")


assert not (OUT / "pre-run-hashes.json").exists(), "Never overwrite preregistered inputs"
assert not subprocess.check_output(["git", "-C", str(SOURCE), "status", "--porcelain"]).strip()
scratch = Path(tempfile.mkdtemp(prefix="mechanism-7b-"))
clean = scratch / "final"
grader = scratch / "grader"
clean.mkdir()
grader.mkdir()
archive(SOURCE, "HEAD", ["src"], clean)
archive(REPO, "60db4b6", ["src", "benchmarks/research_runner.py", "benchmarks/__init__.py"], grader)
sys.path[:0] = [str(clean / "src"), str(grader)]
from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock
from benchmarks.research_runner import _load_cases, _canonical_json, reference_expressions
from geosolver.exact import describe_exact

assert source_tree_hash() == EXPECTED
assert verify_engine_lock() == (True, EXPECTED)
for name in ("final_verifier.py", "verification_numerics.py"):
    paths = list((clean / "src").rglob(name))
    assert len(paths) == 1
    path = paths[0]
    assert path.read_bytes() == (grader / path.relative_to(clean)).read_bytes()
problem_set = OUT.parent / "problem-set/problem-set.json"
groups = json.loads(problem_set.read_text())
records = {r.identifier: r for r in _load_cases(REPO / "benchmarks/cases.jsonl")}
tasks = []
for group in ("hard", "fast_algebraic", "fast_search", "multivalued"):
    for identifier in groups[group]:
        record = records[identifier]
        assert record.dsl_path.is_file()
        input_copy = scratch / "inputs" / (identifier + ".json")
        input_copy.parent.mkdir(exist_ok=True)
        input_copy.write_bytes(record.dsl_path.read_bytes())
        expected = sorted({_canonical_json(describe_exact(v).canonical_key())
                           for ref in record.references for v in reference_expressions(ref)})
        tasks.append({"case_id": identifier, "group": group, "dsl_path": str(record.dsl_path),
                      "input_copy": str(input_copy), "sha256": digest(input_copy),
                      "references": list(record.references), "expected_keys": expected})
assert len(tasks) == 72 and len({t["case_id"] for t in tasks}) == 72
cpus = sorted(os.sched_getaffinity(0))[:16]
assert len(cpus) == 16
files = [problem_set, REPO / "benchmarks/cases.jsonl",
         OUT.parent / "switches/new-switches.patch",
         OUT.parent / "run-7/jssa-ablation-67ad79a-vs-60db4b6.patch",
         OUT.parent / "preregistration-7.md", OUT.parent / "preregistration-7b.md",
         *sorted(OUT.rglob("*.py")), grader / "benchmarks/research_runner.py"]
manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "scratch": str(scratch),
            "clean_source": str(clean), "frozen_grader": str(grader), "source_hash": source_tree_hash(),
            "source_commit": subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip(),
            "source_status_clean": True, "source_files": {str(p.relative_to(clean)): digest(p) for p in sorted(clean.rglob("*")) if p.is_file()},
            "files": {str(p): digest(p) for p in files}, "inputs": tasks,
            "python": sys.executable, "python_version": sys.version, "host": platform.node(),
            "platform": platform.platform(), "cpus": cpus, "parallel": 16, "cores": 1,
            "seeds": [401, 402, 403], "time_limit_seconds": 180, "outer_timeout_seconds": 188,
            "arms": ["BASE", "NO_RESIDUAL_REWRITE", "NO_DIVERSE_SELECTION"],
            "rotation": "seed outer, problem-set group order inner; k=(crc32(case_id.encode())+seed)%3; arms[k:]+arms[:k]",
            "thread_environment": {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
            "time_metric": "worker artifact elapsed_seconds; paired exact-set matches only; C=180 for all nonmatches",
            "D3_aggregation": "literal per-problem criterion: all estimable per-problem medians <=1.0; also report median of those medians, without substituting it for the criterion; unestimable problems listed",
            "probe_method": "verify-log wrappers; persistent mmap smooth-call counter and handoff JSONL survive termination"}
(OUT / "pre-run-hashes.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"scratch": str(scratch), "source_hash": source_tree_hash(), "inputs": len(tasks), "cpus": cpus}))
