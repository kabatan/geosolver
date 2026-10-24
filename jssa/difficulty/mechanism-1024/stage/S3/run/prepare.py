"""Freeze all executable inputs before the first S3 refinement; no solver run."""
import hashlib
import json
import os
import pickle
import platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
S3 = OUT.parent
S1 = S3.parent / "S1"
assert not (OUT / "pre-run-hashes.json").exists()
OLD = json.loads((S1 / "pre-run-hashes.json").read_text())
REPO = Path(OLD["repository"])
ROOT = Path(tempfile.mkdtemp(prefix="mechanism-S3-"))
SRC = Path("/tmp/s3-impl/src")
FROZEN = Path(OLD["scratch"]) / "frozen/src"
sys.path.insert(0, str(SRC))
from geosolver.runtime.integrity import source_tree_hash, installed_dependencies


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def treehash(root):
    h = hashlib.sha256()
    for p in sorted((root / "geosolver").rglob("*")):
        if p.is_file() and p.suffix in {".py", ".json", ".toml"} and p.name != "engine-lock.json" and "__pycache__" not in p.parts and "frontend" not in p.parts:
            h.update(str(p.relative_to(root / "geosolver")).encode() + b"\0" + p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return "sha256:" + h.hexdigest()


assert source_tree_hash() == "sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb"
assert treehash(FROZEN) == OLD["frozen_source_hash"]
IMPL = json.loads((S3 / "impl-hashes.json").read_text())
for name, expected in IMPL["implementation_files_sha256"].items():
    assert sha(SRC / name) == expected, name
contacts = {r["case_id"]: r for r in json.loads((S3 / "contacts.json").read_text())["cases"]}
tasks, copied = [], {}
for i, old in enumerate(OLD["inputs"]):
    task = dict(old, group=contacts[old["case_id"]]["group"])
    task["arm_order"] = ["T0", "T1", "T2"][i % 3:] + ["T0", "T1", "T2"][:i % 3]
    case = task["case_id"]
    d = ROOT / "runs" / case
    d.mkdir(parents=True)
    for name in ("initial.pkl", "initial.json", "scales.json"):
        origin = Path(OLD["scratch"]) / "runs" / case / name
        shutil.copyfile(origin, d / name)
        copied[str(origin)] = sha(origin)
        assert sha(origin) == sha(d / name)
    with (d / "initial.pkl").open("rb") as f:
        candidates, config = pickle.load(f)
    task["candidate_uids"] = [c.candidate_uid for c in candidates]
    task["config_repr"] = repr(config)
    task["initial_sha256"] = sha(d / "initial.pkl")
    task["scales_sha256"] = sha(d / "scales.json")
    origin = Path(task["input_copy"])
    dest = d / "input.json"
    shutil.copyfile(origin, dest)
    assert sha(dest) == task["sha256"] == contacts[case]["input_sha256"]
    assert sha(Path(task["dsl_path"])) == task["sha256"]
    task["input_copy"] = str(dest)
    baseline = Path(OLD["scratch"]) / "runs" / case / "BASE.measure.json"
    shutil.copyfile(baseline, d / "S1-BASE.measure.json")
    copied[str(baseline)] = sha(baseline)
    tasks.append(task)
files = [S3 / "rules.md", *sorted(OUT.glob("*.py"))]
files += [S3 / n for n in ("preregistration-10.md", "README.md", "contacts.json", "switch.patch", "impl-hashes.json", "switch-check.md", "switch-check.json")]
files += [S1 / n for n in ("rules.md", "worker.py", "driver.py", "prepare.py", "repair_measurement.py", "repair_references.py", "pre-run-hashes.json")]
files += [REPO / "benchmarks/cases.jsonl", REPO / "benchmarks/research_runner.py"]
source_files = {str(p): sha(p) for root in (SRC, FROZEN) for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
M = dict(created_utc=datetime.now(timezone.utc).isoformat(), scratch=str(ROOT),
    source_origin=str(SRC), frozen_origin=str(FROZEN), source_hash=source_tree_hash(), frozen_source_hash=OLD["frozen_source_hash"],
    repository=str(REPO), output=str(OUT), inputs=tasks, files={str(p): sha(p) for p in files},
    source_files=source_files, s1_saved_inputs=copied,
    cpus=sorted(os.sched_getaffinity(0))[:2], parallel=2, cores=1, seeds=[0],
    python=OLD["python"], python_version=sys.version, dependencies=installed_dependencies(), host=platform.node(), platform=platform.platform(),
    thread_environment={k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")},
    seconds=dict(refine=90, verify=90, measurement_outer=90), initial_loadavg=list(os.getloadavg()),
    switch_settings={**{a: {"GEOSOLVER_S3_TANGENCY_MODE": a} for a in ("T0", "T1", "T2")}, "verify": {}, "references": {}, "ablations": "all unset"},
    trace_case="AIME-2018-II-14", main_search_executed=False)
assert len(M["cpus"]) == 2 and sum(len(t["candidate_uids"]) for t in tasks) == 224
(ROOT / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=2)+"\n")
(OUT / "pre-run-hashes.json").write_text((ROOT / "manifest.json").read_text())
(OUT / "progress.md").write_text(f"# S3 進捗\n\n実行前hash固定済み。2並列、1工程1コア、内部スレッド1。\n生データ: `{ROOT}`\n")
print(ROOT)
