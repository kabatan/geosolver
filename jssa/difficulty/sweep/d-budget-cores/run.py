"""Q43d: frozen public CLI, fixed sample, <=3 one-core solver processes.

No solver hooks. Full public outputs and host telemetry live under /tmp.
The historical runner is loaded from git, solely for fingerprinting and grading.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import datetime as dt
import fcntl
import gzip
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import threading
import time
import traceback
import types

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
COMMIT = "60db4b679b04167175c51c479c87c22fa663fda0"
SOURCE = "sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5"
SELECT_SEED = 2026102404
SEEDS = [430401, 430501, 430601, 430701]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
import psutil


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def save(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path.is_relative_to(BASE) and len(payload.encode()) > 4_900_000:
        raise ValueError("repository summary exceeds size ceiling")
    if exclusive:
        with path.open("x") as f:
            f.write(payload)
    else:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(payload)
        temp.replace(path)


def frozen_runner():
    code = subprocess.check_output(["git", "show", f"{COMMIT}:benchmarks/research_runner.py"], cwd=ROOT)
    module = types.ModuleType("q43d_frozen_research_runner")
    module.__file__ = str(ROOT / "benchmarks/research_runner.py")
    sys.modules[module.__name__] = module
    exec(compile(code, module.__file__, "exec"), module.__dict__)
    return module, hashlib.sha256(code).hexdigest()


RR, RR_SHA = frozen_runner()


def verify():
    from geosolver.runtime.integrity import verify_engine_lock
    fp = RR.runtime_fingerprint()
    assert fp["source_hash"] == SOURCE and not fp["issues"], fp
    assert verify_engine_lock()[0]
    assert fp["import_root"] == str(ROOT / "src/geosolver")
    assert not subprocess.check_output(["git", "diff", COMMIT, "--", "src"], cwd=ROOT)
    assert not subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "src"], cwd=ROOT)
    assert "sitecustomize" not in sys.modules
    return fp


def prepare():
    fp = verify()
    assert not (BASE / "manifest.json").exists(), "refuse to replace a fixed sample"
    from geosolver.exact import describe_exact
    from geosolver.problem.models import GeometryProblem
    from geosolver.problem.validation import validate
    selected = []
    populations = []
    for group, rel in [("dev", "benchmarks/cases.jsonl"),
                       ("postfreeze2026", "jssa/difficulty/new2026/cases.jsonl")]:
        path = ROOT / rel
        records = RR._load_cases(path)
        ranked = sorted(records, key=lambda r: (hashlib.sha256(
            f"{SELECT_SEED}:{group}:{r.identifier}".encode()).hexdigest(), r.identifier))
        populations.append({"group": group, "path": rel, "n": len(records), "sha256": sha(path)})
        for rank, r in enumerate(ranked[:10]):
            assert r.runnable and r.truth_status == "verified"
            assert json.loads(r.dsl_path.read_text()) == r.dsl
            report = validate(GeometryProblem.model_validate(r.dsl))
            expected = sorted({canonical(describe_exact(v).canonical_key())
                               for ref in r.references for v in RR.reference_expressions(ref)})
            selected.append({"id": r.identifier, "group": group, "rank": rank,
                             "dsl_path": str(r.dsl_path.relative_to(ROOT)), "dsl_sha256": sha(r.dsl_path),
                             "references": list(r.references), "expected_keys": expected,
                             "n_vars": len(r.dsl["variables"]), "validation_valid": report.valid,
                             "validation_issues": [v.model_dump(mode="json") for v in report.issues],
                             "time_sweep": rank < 2})
    selected.sort(key=lambda r: (r["rank"], r["group"]))
    jobs = []
    for i, case in enumerate(selected):
        block = []
        rng = random.Random(SELECT_SEED + i)
        for seed in SEEDS[:2]:
            cores = [1, 2, 4, 8]
            rng.shuffle(cores)
            block.extend((seed, 180, c, "cores") for c in cores)
        block.extend((seed, 180, 1, "extra_seed") for seed in SEEDS[2:])
        if case["time_sweep"]:
            budgets = [(s, t, 1, "budget_subset") for s in SEEDS[:2] for t in (360, 900)]
            rng.shuffle(budgets)
            # Alternate insertion at the front/back to avoid a uniformly late long-budget block.
            block = budgets + block if i % 2 else block + budgets
        for seed, budget, cores, purpose in block:
            jobs.append({"job": f"j{len(jobs):03d}", "case_index": i, "id": case["id"],
                         "lane": i % 3, "seed": seed, "budget": budget,
                         "cores": cores, "purpose": purpose})
    raw = Path("/tmp") / f"q43d-budget-cores-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    raw.mkdir()
    save(BASE / "manifest.json", {"created_utc": now(), "frozen_commit": COMMIT,
         "source_hash": SOURCE, "frozen_runner_sha256": RR_SHA, "runtime_fingerprint": fp,
         "selection_seed": SELECT_SEED,
         "selection_rule": "Within each complete corpus, ascending (SHA256(f'{seed}:{group}:{id}'), id), take first 10. No outcome or dimension filtering.",
         "populations": populations, "cases": selected, "seeds": SEEDS, "raw_root": str(raw),
         "jobs": jobs, "job_count": len(jobs), "max_solver_concurrency": 3,
         "cores_meaning": "Public --cores request; frozen service.py forces effective cores=1. No implementation patch.",
         "unseen_meaning": "2026 corpus was authored after solver freeze, but has been used by other experiments. This is exploratory, not a fresh confirmatory holdout.",
         "budget_subset_rule": "First 2 hash-ranked cases of each corpus, 4 total; same 2 primary seeds at 360 and 900 seconds.",
         "outer_watchdog_extra_seconds": 8,
         "seed_aggregation": "Per-case prefix groups [430401,430501] and [430601,430701]; both any-correct and exact equality of union of public answer sets, including failures in the denominator.",
         "failure_rule": "All selected cases and scheduled jobs retained. Timeout, crash, input/contract error score false; missing evidence remains unknown for mechanism claims.",
         "adapter_sha256": sha(__file__)}, exclusive=True)
    with (BASE / "selection.csv").open("x") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "group", "rank", "n_vars", "time_sweep", "dsl_path", "dsl_sha256"])
        writer.writeheader()
        writer.writerows({k: c[k] for k in writer.fieldnames} for c in selected)
    with (BASE / "jobs.csv").open("x") as f:
        writer = csv.DictWriter(f, fieldnames=list(jobs[0]))
        writer.writeheader()
        writer.writerows(jobs)
    print(json.dumps({"jobs": len(jobs), "raw_root": str(raw), "selected": [c["id"] for c in selected]}, ensure_ascii=False), flush=True)


def choose_cpus():
    allowed = sorted(os.sched_getaffinity(0))
    groups = {}
    for cpu in allowed:
        top = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        key = ((top / "physical_package_id").read_text().strip(), (top / "core_id").read_text().strip())
        groups.setdefault(key, []).append(cpu)
    samples = [psutil.cpu_percent(interval=1, percpu=True) for _ in range(3)]
    ranked = sorted(groups.values(), key=lambda cpus: (sum(v[c] for v in samples for c in cpus) / len(samples), cpus[0]))
    chosen = []
    errors = []
    for cpus in ranked:
        try:
            os.sched_setaffinity(0, {cpus[0]})
            assert os.sched_getaffinity(0) == {cpus[0]}
            chosen.append(cpus[0])
        except Exception as e:
            errors.append(str(e))
        finally:
            os.sched_setaffinity(0, allowed)
        if len(chosen) == 3:
            break
    assert len(chosen) == 3, errors
    return {"chosen": chosen, "physical_siblings": list(groups.values()), "samples": samples,
            "load": os.getloadavg(), "utc": now(), "exclusive_reservation": False,
            "rule": "3 distinct physical cores with least summed sibling use over 3 one-second samples, fixed throughout campaign.",
            "pid_visibility": "Namespace may hide other users' processes; host load and per-CPU use capture interference, not its owner."}


def environment(raw):
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("PYTHON", "GEOSOLVER", "Q30", "Q36", "Q37", "Q43", "LD_")):
            del env[key]
    env.update(PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]), PYTHONHASHSEED="0",
               PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(raw / "tmp"), **RR.THREAD_ENVIRONMENT)
    return env


def finite_float(value):
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (ValueError, TypeError):
        return None


def compact(result, case, cpu):
    result = result or {}
    diagnostics = result.get("diagnostics") or {}
    info = diagnostics.get("process_info") or {}
    summary = diagnostics.get("pipeline_summary") or {}
    issues = []
    if result and result.get("engine", {}).get("source_hash") != SOURCE:
        issues.append("source_hash")
    if result.get("status") in ("solved", "no_answer_found"):
        if info.get("import_root") != str(ROOT / "src/geosolver"):
            issues.append("import_root")
        if info.get("cpu_affinity") != [cpu]:
            issues.append("affinity")
    keys = RR._answer_keys(result)
    accepted = [c for c in diagnostics.get("candidate_records", []) if c.get("accepted")]
    witnesses = []
    for c in accepted:
        x = [finite_float(v) for v in c.get("x_hp", [])]
        source = c.get("source") or {}
        witnesses.append({"uid": c.get("candidate_uid"), "revision": c.get("revision"), "x": x,
                          "answer": finite_float(c.get("answer_hp")), "residual": finite_float(c.get("residual_norm_hp")),
                          "backend": source.get("origin_backend"), "phase": source.get("origin_phase")})
    normal = result.get("status") in ("solved", "no_answer_found") and not issues
    return {"status": result.get("status", "artifact_missing"), "termination": result.get("termination_reason"),
            "error": result.get("error"), "contract_issues": issues, "normal": normal,
            "matched": bool(normal and keys == case["expected_keys"]), "answer_keys": keys,
            "requested_resources": result.get("requested_resources"), "used_resources": result.get("used_resources"),
            "solver_elapsed": result.get("elapsed_seconds"), "process_info": info,
            "phase_timings": diagnostics.get("phase_timings", {}), "counters": diagnostics.get("counters", {}),
            "numeric_feasible": diagnostics.get("numeric_feasible"),
            "accepted_count": len(accepted), "candidate_count": len(diagnostics.get("candidate_records", [])),
            "exact_assembly": {k: v for k, v in (summary.get("exact_assembly") or {}).items()
                               if isinstance(v, (int, float, bool, str)) or v is None},
            "witnesses": witnesses}


def kill_owned(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def execute(job, case, cpu, raw, manifest):
    dest = BASE / "receipts" / f"{job['job']}.json"
    started_file = raw / "starts" / f"{job['job']}.json"
    if dest.exists():
        return
    if started_file.exists():
        raise RuntimeError(f"previously started {job['job']} lacks final receipt; investigate, never silently rerun")
    dsl = ROOT / case["dsl_path"]
    assert sha(dsl) == case["dsl_sha256"]
    assert verify()["source_hash"] == SOURCE
    output = raw / "outputs" / f"{job['job']}.json"
    command = ["taskset", "-c", str(cpu), sys.executable, "-m", "geosolver.application.cli", "solve", str(dsl),
               "--time-limit-seconds", str(job["budget"]), "--cores", str(job["cores"]),
               "--seed", str(job["seed"]), "--output", str(output)]
    start = {**job, "cpu": cpu, "started_utc": now(), "load_start": os.getloadavg(), "command": command,
             "source_hash": SOURCE, "dsl_sha256": case["dsl_sha256"], "manifest_sha256": sha(BASE / "manifest.json")}
    save(started_file, start, exclusive=True)
    begun = time.monotonic()
    timed_out = False
    with (raw / "logs" / f"{job['job']}.stdout").open("w") as out, (raw / "logs" / f"{job['job']}.stderr").open("w") as err:
        proc = subprocess.Popen(command, cwd=ROOT, env=environment(raw), stdout=out, stderr=err, start_new_session=True)
        save(raw / "active" / f"lane{job['lane']}.json", {**job, "pid": proc.pid, "cpu": cpu, "started_utc": start["started_utc"]})
        try:
            proc.wait(timeout=job["budget"] + 8)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_owned(proc)
        finally:
            # Kill only this process's private group, including any lingering children.
            kill_owned(proc)
    elapsed = time.monotonic() - begun
    result = None
    parse_error = None
    compressed_hash = None
    if output.exists():
        try:
            result = json.loads(output.read_text())
        except Exception as exc:
            parse_error = repr(exc)
        data_hash = sha(output)
        original_bytes = output.stat().st_size
        compressed = output.with_suffix(".json.gz")
        with output.open("rb") as source, gzip.open(compressed, "wb", compresslevel=1) as target:
            import shutil
            shutil.copyfileobj(source, target)
        compressed_hash = sha(compressed)
        output.unlink()
    else:
        data_hash, original_bytes = None, 0
    detail = compact(result, case, cpu)
    if timed_out or parse_error:
        detail.update(matched=False, normal=False)
    witnesses = detail.pop("witnesses")
    save(raw / "witnesses" / f"{job['job']}.json", witnesses)
    receipt = {**start, "finished_utc": now(), "wall_seconds": elapsed, "load_end": os.getloadavg(),
               "returncode": proc.returncode, "outer_timeout": timed_out, "parse_error": parse_error,
               "raw_sha256": data_hash, "raw_bytes": original_bytes, "gzip_sha256": compressed_hash, **detail,
               "witness_path": str(raw / "witnesses" / f"{job['job']}.json")}
    save(dest, receipt, exclusive=True)
    save(raw / "active" / f"lane{job['lane']}.json", {"idle": True, "finished_job": job["job"]})
    print(f"{job['job']} {job['id']} seed={job['seed']} c={job['cores']} t={job['budget']} {detail['status']} matched={detail['matched']} wall={elapsed:.1f}", flush=True)


def supervise():
    manifest = json.loads((BASE / "manifest.json").read_text())
    raw = Path(manifest["raw_root"])
    for folder in ("outputs", "logs", "starts", "active", "tmp", "witnesses"):
        (raw / folder).mkdir(exist_ok=True)
    lock = (raw / "supervisor.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    verify()
    affinity_path = BASE / "cpu-selection.json"
    affinity = json.loads(affinity_path.read_text()) if affinity_path.exists() else choose_cpus()
    if not affinity_path.exists():
        save(affinity_path, affinity, exclusive=True)
    stop = threading.Event()

    def monitor():
        with (raw / "host-telemetry.jsonl").open("a") as f:
            while not stop.is_set():
                usage = psutil.cpu_percent(interval=1, percpu=True)
                row = {"utc": now(), "load": os.getloadavg(), "percpu": usage,
                       "available_memory": psutil.virtual_memory().available,
                       "tmp_free": psutil.disk_usage(str(raw)).free}
                f.write(canonical(row) + "\n")
                f.flush()
                stop.wait(4)

    def lane(index):
        for job in manifest["jobs"]:
            if job["lane"] == index:
                execute(job, manifest["cases"][job["case_index"]], affinity["chosen"][index], raw, manifest)

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    save(BASE / "execution-start.json", {"utc": now(), "manifest_sha256": sha(BASE / "manifest.json"),
         "runner_sha256": sha(__file__), "runtime_fingerprint": verify(), "cpus": affinity["chosen"],
         "max_solver_jobs": 3, "blas_threads": 1}, exclusive=not (BASE / "execution-start.json").exists())
    errors = []
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(lane, i) for i in range(3)]
            for future in futures:
                try:
                    future.result()
                except Exception:
                    errors.append(traceback.format_exc())
    finally:
        stop.set()
        monitor_thread.join(timeout=7)
        save(BASE / "execution-end.json", {"utc": now(), "completed": len(list((BASE / "receipts").glob("*.json"))),
             "scheduled": len(manifest["jobs"]), "errors": errors, "runtime_fingerprint": verify()})
    if errors:
        raise RuntimeError(errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run"))
    args = parser.parse_args()
    prepare() if args.action == "prepare" else supervise()
