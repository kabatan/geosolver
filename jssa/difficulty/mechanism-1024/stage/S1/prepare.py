"""Copy sources read-only in spirit, then freeze input and script hashes."""
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[4]
assert (REPO / "benchmarks/cases.jsonl").exists()
assert not (OUT / "pre-run-hashes.json").exists()
ROOT = Path(tempfile.mkdtemp(prefix="mechanism-S1-"))
shutil.copytree("/tmp/mechanism-7b-lkdjle5l/final/src", ROOT / "final/src", ignore=shutil.ignore_patterns("__pycache__"))
shutil.copytree("/tmp/mech-inv-clean/src", ROOT / "frozen/src", ignore=shutil.ignore_patterns("__pycache__"))
sys.path.insert(0, str(ROOT / "final/src"))
from geosolver.runtime.integrity import source_tree_hash, installed_dependencies
SOURCE = source_tree_hash()
assert SOURCE == "sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sourcehash(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in {".py", ".json", ".toml"} and p.name != "engine-lock.json" and "__pycache__" not in p.parts and "frontend" not in p.parts:
            h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return "sha256:" + h.hexdigest()


frozen_hash = sourcehash(ROOT / "frozen/src/geosolver")
assert frozen_hash.startswith("sha256:d8fd9bb8")
verification_files = {}
for p in sorted((ROOT / "final/src/geosolver/engine/standard/evaluation").glob("*.py")):
    if p.name == "final_verifier.py" or p.name.startswith("verification_"):
        assert p.read_bytes() == (ROOT / "frozen/src" / p.relative_to(ROOT / "final/src")).read_bytes()
        verification_files[p.name] = sha(p)
sys.path.insert(0, str(REPO))
from benchmarks.research_runner import reference_expressions
CASES = ["AIME-2015-II-15", "AIME-2018-II-14", "HMMT-2008-FEB-GEO-09", "HMMT-2009-FEB-GEO-10", "HMMT-2010-FEB-GEO-09", "HMMT-2020-FEB-GEO-09", "HMMT-2022-FEB-GEO-10", "HMMT-2023-FEB-GEO-07", "JMO-2013-PRE-05", "JMO-2024-PRE-06", "aime-2001-2-7", "aime-2002-2-14"]
P1 = [CASES[i] for i in (1, 2, 6, 7, 8, 9, 11)]
records = {d["id"]: d for d in map(json.loads, (REPO / "benchmarks/cases.jsonl").read_text().splitlines())}
tasks = []
(ROOT / "inputs").mkdir()
for i, identifier in enumerate(CASES):
    row = records[identifier]
    original = REPO / "benchmarks" / row["dsl_path"]
    copied = ROOT / "inputs" / (identifier + ".json")
    shutil.copyfile(original, copied)
    refs = row["answer"] if isinstance(row["answer"], list) else [row["answer"]]
    tasks.append({"case_id": identifier, "p1_group": identifier in P1, "seed": 0,
        "dsl_path": str(original), "input_copy": str(copied), "sha256": sha(copied),
        "references": refs, "reference_expressions": [e for ref in refs for e in reference_expressions(ref)],
        "arm_order": ["BASE", "NO_RESIDUAL_REWRITE"] if i % 2 == 0 else ["NO_RESIDUAL_REWRITE", "BASE"]})
files = [OUT / n for n in ("rules.md", "prepare.py", "worker.py", "driver.py", "analyze.py")]
files += [REPO / "benchmarks/cases.jsonl", REPO / "benchmarks/research_runner.py", OUT.parents[1] / "preregistration-7.md"]
files += sorted((REPO / "jssa/results/tangency-signed").rglob("*"))
files = [p for p in files if p.is_file()]
manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "scratch": str(ROOT),
    "source_origin": "/tmp/mechanism-7b-lkdjle5l/final/src", "frozen_origin": "/tmp/mech-inv-clean/src",
    "source_hash": SOURCE, "frozen_source_hash": frozen_hash, "verification_files_identical": verification_files,
    "files": {str(p): sha(p) for p in files},
    "source_files": {str(p.relative_to(ROOT)): sha(p) for p in sorted(ROOT.rglob("*")) if p.is_file()},
    "inputs": tasks, "python": sys.executable, "python_version": sys.version,
    "dependencies": installed_dependencies(), "host": platform.node(), "platform": platform.platform(),
    "cpus": sorted(os.sched_getaffinity(0))[:2], "parallel": 2, "cores": 1, "seeds": [0],
    "thread_environment": {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
    "switch_settings": {"search": {}, "BASE": {}, "NO_RESIDUAL_REWRITE": {"GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE": "1"}, "verify": {}},
    "seconds": {"search_pipeline_budget": 178, "search_outer": 180, "refine": 90, "verify": 90, "measurement_outer": 90},
    "initial_loadavg": list(os.getloadavg()), "repository": str(REPO), "output": str(OUT)}
(ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
(OUT / "pre-run-hashes.json").write_text((ROOT / "manifest.json").read_text())
(OUT / "progress.md").write_text(f"# S1 進捗\n\n準備完了。対象実行前の入力・ルール・スクリプトhashを固定。\n\n一時保存先: `{ROOT}`\n")
print(ROOT)
