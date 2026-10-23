"""Q19 frozen campaign. Never assess, print, or summarize solver answers."""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
sys.dont_write_bytecode = True
sys.setrecursionlimit(10000)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"

import argparse
import concurrent.futures
import datetime
import fcntl
import hashlib
import json
import multiprocessing
import shutil
import subprocess
import tarfile
import time
import traceback

import psutil
from benchmarks import research_runner as research
from geosolver.problem.models import GeometryProblem
from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock

FROZEN_COMMIT = "60db4b679b04167175c51c479c87c22fa663fda0"
SOURCE_HASH = "sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5"
MULTIPLICITY_HASH = "7b845d25863158f2023e4640aa5b37141b1c227caf199a7ec4ab235fd2541e11"
RAW_BASE = ROOT.parent / "sealed-raw"
DESTINATION = RAW_BASE / "q19-frozen-201-205"
SEEDS = [201, 202, 203, 204, 205]
JOBS = 8
CPU = None


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, data):
    research._atomic_json(Path(path), data)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def fingerprint():
    entries = [(str(p.relative_to(ROOT)), sha(p)) for p in sorted((ROOT / "src").rglob("*.py"))]
    multiplicity = hashlib.sha256(json.dumps(entries).encode()).hexdigest()
    assert len(entries) == 246 and multiplicity == MULTIPLICITY_HASH
    assert source_tree_hash() == SOURCE_HASH
    valid, detail = verify_engine_lock()
    assert valid, detail
    assert not git("diff", FROZEN_COMMIT, "--", "src")
    assert git("rev-parse", "HEAD:src") == git("rev-parse", FROZEN_COMMIT + ":src")
    runtime = research.runtime_fingerprint()
    assert not runtime["issues"], "runtime dependencies/import root mismatch"
    return {"checked_at_utc": now(), "source_hash": SOURCE_HASH,
            "multiplicity_src_py_sha256": multiplicity, "src_py_count": len(entries),
            "frozen_commit": FROZEN_COMMIT, "head": git("rev-parse", "HEAD"),
            "src_git_tree": git("rev-parse", "HEAD:src"), "runtime": runtime,
            "engine_lock_verified": True, "src_diff_from_frozen_empty": True}


def preflight():
    identity = fingerprint()
    cases = [json.loads(line) for line in (CORPUS / "cases.jsonl").read_text().splitlines()]
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    selected = [row for row in manifest["rows"] if row["status"] == "selected_candidate"]
    freeze = json.loads((CORPUS / "revisions/v3-input-freeze.json").read_text())
    assert len(cases) == len(selected) == len({case["id"] for case in cases}) == 54
    assert [case["id"] for case in cases] == [row["id"] for row in selected]
    assert sha(CORPUS / "manifest.json") == freeze["manifest_sha256"]
    for case, row in zip(cases, selected, strict=True):
        assert not {"answer", "official_answer", "secondary_answer", "solution"} & case.keys()
        path = CORPUS / case["dsl_path"]
        assert sha(path) == row["input_sha256"] == freeze["input_hashes"][case["id"]]
        assert json.loads(path.read_text()) == case["dsl"]
        GeometryProblem.model_validate(case["dsl"])
    cpus = research._independent_cpus()[:JOBS]
    assert len(cpus) == JOBS and None not in cpus
    identity.update({"case_count": 54, "planned_runs": 270, "seeds": SEEDS,
                     "jobs": JOBS, "cpus": cpus, "time_limit_seconds": 180,
                     "cores": 1, "external_watchdog_seconds": 188})
    return identity, cases


def prepare(identity, cases):
    DESTINATION.mkdir(parents=True, exist_ok=False)
    inputs = DESTINATION / "inputs"
    (inputs / "dsl").mkdir(parents=True)
    for name in ("manifest.json", "cases.jsonl", "README.md", "build_cases.py", "verify_static.py"):
        shutil.copyfile(CORPUS / name, inputs / name)
    shutil.copyfile(CORPUS / "revisions/v3-input-freeze.json", inputs / "v3-input-freeze.json")
    for case in cases:
        shutil.copyfile(CORPUS / case["dsl_path"], inputs / case["dsl_path"])
    # All solver inputs are the fixed snapshots, never the concurrently audited originals.
    validation = research.validate_corpus(inputs / "cases.jsonl")
    write_json(DESTINATION / "input-validation.json", validation)
    assert validation["valid"] and validation["runnable_count"] == 54
    shutil.copytree(HERE / "hook", DESTINATION / "runner-source/hook")
    shutil.copyfile(__file__, DESTINATION / "runner-source/run_sealed.py")
    shutil.copyfile(ROOT / "benchmarks/research_runner.py", DESTINATION / "runner-source/research_runner.py")
    metadata = {**identity, "created_at_utc": now(), "command": sys.argv,
                "excluded_before_run": 0, "assessment_performed": False,
                "audit_results_read": False,
                "inputs": {str(p.relative_to(inputs)): sha(p) for p in sorted(inputs.rglob("*")) if p.is_file()},
                "runner_source": {str(p.relative_to(DESTINATION)): sha(p)
                                  for p in sorted((DESTINATION / "runner-source").rglob("*")) if p.is_file()},
                "candidate_capture": "passive FloatCandidate post-init field serialization",
                "temporary_artifacts": "retained without cleanup; TMPDIR is per run",
                "python_recursion_limit": 10000,
                "input_accommodation": "all processes use recursionlimit=10000; pre-solver default-limit validation failed on a 335-term sum; no DSL rewrite",
                "intervention": None}
    write_json(DESTINATION / "campaign-manifest.json", metadata)


def initialize_worker(cpu_queue):
    global CPU
    CPU = cpu_queue.get()
    psutil.Process().cpu_affinity([CPU])


def run_one(task):
    identifier, seed = task
    capture = DESTINATION / "evidence" / identifier / str(seed)
    capture.mkdir(parents=True, exist_ok=False)
    temporary = capture / "temporary"
    temporary.mkdir()
    os.environ.update({"Q19_CAPTURE_ROOT": str(capture), "TMPDIR": str(temporary),
                       "TMP": str(temporary), "TEMP": str(temporary),
                       "PYTHONPATH": os.pathsep.join([str(DESTINATION / "runner-source/hook"), str(ROOT / "src"), str(ROOT)])})
    import tempfile
    tempfile.tempdir = str(temporary)
    records = research._load_cases(DESTINATION / "inputs/cases.jsonl")
    record = next(row for row in records if row.identifier == identifier)
    issue = False
    try:
        research._run_one(record, seed, DESTINATION, CPU)
    except BaseException:
        # Keep exceptions inside the sealed tree. Never print worker messages.
        issue = True
        (capture / "runner-error.txt").write_text(traceback.format_exc())
    raw_path = DESTINATION / "runs" / identifier / f"{seed}.json"
    timeout, error, contract_issue, capture_error = False, issue, False, False
    if raw_path.exists():
        raw = json.loads(raw_path.read_text())
        process = raw.get("process", {})
        result = raw.get("solver_result") or {}
        # Only project to operational flags; never access answers, numeric values,
        # feasibility/acceptance counts, or reference data.
        timeout = bool(process.get("timed_out")) or result.get("termination_reason") == "time_limit_reached"
        error = error or process.get("returncode") != 0 or not result or result.get("status") not in {
            "solved", "no_answer_found"}
        contract_issue = bool(raw.get("execution_contract_issues"))
        capture_error = not (capture / "cli-capture-installed.json").exists()
        # Invalid inputs may return before spawning a numerical worker; this is
        # recorded as an error, never excluded or rerun after seeing results.
        if result.get("status") in {"solved", "no_answer_found"}:
            capture_error |= not (capture / "worker-capture-installed.json").exists()
    else:
        error = True
    receipt = {"raw_saved": raw_path.exists(), "error": bool(error), "timeout": bool(timeout),
               "contract_issue": contract_issue, "capture_error": bool(capture_error)}
    write_json(capture / "operational-receipt.json", receipt)
    return receipt


def counts():
    receipts = list((DESTINATION / "evidence").glob("*/*/operational-receipt.json"))
    values = [json.loads(p.read_text()) for p in receipts]
    return {"planned": 270, "finished": len(values),
            **{key: sum(bool(row[key]) for row in values)
               for key in ("raw_saved", "error", "timeout", "contract_issue", "capture_error")}}


def seal():
    summary = counts()
    assert summary["finished"] == summary["raw_saved"] == 270
    after = fingerprint()
    before = json.loads((DESTINATION / "campaign-manifest.json").read_text())
    for relative, expected in before["inputs"].items():
        assert sha(DESTINATION / "inputs" / relative) == expected
    for relative, expected in before["runner_source"].items():
        assert sha(DESTINATION / relative) == expected
    write_json(DESTINATION / "completion.json", {
        **summary, "completed_at_utc": now(), "postflight": after,
        "assessment_performed": False, "answers_accessed_for_summary": False,
    })
    # Hash bytes without examining results; file hashes remain INSIDE the seal.
    files = sorted(p for p in DESTINATION.rglob("*") if p.is_file())
    write_json(DESTINATION / "file-sha256.json", {
        str(p.relative_to(DESTINATION)): sha(p) for p in files
    })
    archive = RAW_BASE / "q19-frozen-201-205.tar"
    assert not archive.exists(), "never overwrite an existing seal"
    with tarfile.open(archive, mode="x", format=tarfile.GNU_FORMAT) as tar:
        for path in sorted(p for p in DESTINATION.rglob("*") if p.is_file()):
            info = tar.gettarinfo(str(path), arcname="q19-frozen-201-205/" + path.relative_to(DESTINATION).as_posix())
            assert info.isfile()
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            info.pax_headers = {}
            with path.open("rb") as stream:
                tar.addfile(info, stream)
    seal_metadata = {"sha256": sha(archive), "archive": str(archive),
                     "sealed_at_utc": now(), "bytes": archive.stat().st_size,
                     "file_count": len(files) + 1, "operational_counts": summary}
    write_json(RAW_BASE / "q19-seal-receipt.json", seal_metadata)
    print(json.dumps(seal_metadata, ensure_ascii=False), flush=True)


def run():
    identity, cases = preflight()
    prepare(identity, cases)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    for cpu in identity["cpus"]:
        queue.put(cpu)
    tasks = [(case["id"], seed) for case in cases for seed in SEEDS]
    print(json.dumps({"started_at_utc": now(), "planned": len(tasks), "jobs": JOBS}), flush=True)
    last_report = time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=JOBS, mp_context=context, initializer=initialize_worker, initargs=(queue,),
    ) as pool:
        futures = [pool.submit(run_one, task) for task in tasks]
        pending = set(futures)
        while pending:
            done, pending = concurrent.futures.wait(pending, timeout=30,
                                                    return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                future.result()
            if time.monotonic() - last_report >= 55 or not pending:
                print(json.dumps(counts()), flush=True)
                last_report = time.monotonic()
    seal()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["preflight", "run", "progress"])
    action = parser.parse_args().action
    if action == "preflight":
        identity, _ = preflight()
        print(json.dumps(identity, ensure_ascii=False))
    elif action == "progress":
        print(json.dumps(counts()))
    else:
        RAW_BASE.mkdir(parents=True, exist_ok=True)
        with (RAW_BASE / "q19-runner.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run()


if __name__ == "__main__":
    main()
