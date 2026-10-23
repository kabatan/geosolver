"""Fixed preregistration-4 campaign. No production run without --full."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"

import argparse
import csv
import hashlib
import json
import platform
import socket
import threading
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager

import psutil
from benchmarks import research_runner as research

PREDICTIONS = ROOT / "jssa/difficulty/start-feasibility-1023/predictions.csv"
PREREG = ROOT / "jssa/difficulty/start-feasibility-1023/preregistration-4.md"
CONDITIONS = ("normal", "redraw")
SMOKE_IDS = ("AIME-2023-I-12", "HMMT-2024-FEB-GEO-04", "AIME-2014-I-13")
FROZEN_HASH = "sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5"
FIXED_INPUT_HASHES = {
    PREDICTIONS: "be3ad30ddbe312b8756b08cea6f2827c9b996419ec1cd7e31435039583954f78",
    PREREG: "ae442e7a170cf334274be2b1e9eb42bca23e4fabc296197f7d899e2dd3e43ecc",
}


@contextmanager
def campaign_lock(destination):
    """OS releases this lock after a crash; a second runner cannot duplicate runs."""
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "runner.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            lock = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            unlock = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            lock = lambda: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            unlock = lambda: fcntl.flock(stream, fcntl.LOCK_UN)
        try:
            lock()
        except OSError as exc:
            raise RuntimeError("another runner is using this output directory") from exc
        try:
            yield
        finally:
            unlock()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    # Portable across Git's Windows CRLF conversion.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def prediction_rows():
    with PREDICTIONS.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 150 or len({r["id"] for r in rows}) != 150:
        raise ValueError("expected the fixed 150 predictions")
    return rows


def loadavg():
    # Windows psutil.getloadavg returns artificial zeroes for its first 5 s.
    # Use the OS metric only where it exists; never report zero as a substitute.
    try:
        return list(os.getloadavg())
    except (AttributeError, OSError):
        return None


def cpus_for_jobs(jobs):
    try:
        cpus = research._independent_cpus()
    except (AttributeError, OSError, psutil.Error):
        cpus = [None] * (psutil.cpu_count(logical=False) or 1)
    if not 1 <= jobs <= len(cpus):
        raise ValueError(f"jobs must be 1..{len(cpus)}")
    return cpus[:jobs]


def portable_pin(process, cpu=None):
    try:
        return research._redraw_original_pin(process, cpu)
    except (research.CampaignError, AttributeError, OSError, psutil.Error):
        # Worker still requests --cores 1, and all numerical thread envs are 1.
        return None


def summarize_audit(path, condition):
    events = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # A killed worker may leave its final line incomplete.
                events.append({"event": "truncated"})
    installed = [r for r in events if r["event"] == "installed"]
    generated = [r for r in events if r["event"] == "generated"]
    consumed = [r for r in events if r["event"] == "consumed"]
    originals = [r["builder_is_original"] for r in events if "builder_is_original" in r]
    bad = sum(r["event"] in {"mismatch", "truncated"} for r in events)
    matched = sum(r["matches_generated"] for r in consumed)
    verified = (len(installed) == 1 and bool(originals) and not bad
                and all(x == (condition == "normal") for x in originals)
                and (condition == "normal" or matched == len(consumed)))
    return dict(
        hook_installed=len(installed), builder_patched=bool(originals) and not originals[0],
        audit_verified=verified, audit_bad_events=bad,
        starts_generated=len(generated), starts_consumed=len(consumed),
        starts_scheduled=sum(r["event"] == "scheduled" for r in events),
        consumed_matching_generated=matched,
        redraws_generated=sum(r["retries"] for r in generated),
        redraws_consumed=sum(r["retries"] for r in consumed),
        generated_exhausted=sum(r["attempts"] == 2001 and not r["hard_feasible"] for r in generated),
        generated_hard_fraction=(sum(r["hard_feasible"] for r in generated) / len(generated)
                                 if generated else None),
        consumed_hard_fraction=(sum(r["hard_feasible"] for r in consumed) / len(consumed)
                                if consumed else None),
    )


def run_one(task):
    """Reuse the historical CLI invocation, deadlines, process tree, and checks."""
    identifier, seed, condition, destination_text, cpu, ordinal = task
    destination = Path(destination_text)
    campaign = destination / condition
    record = next(r for r in research._load_cases() if r.identifier == identifier)
    run_dir = campaign / "runs" / identifier
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / f"{seed}.json"
    receipt_path = run_dir / f"{seed}.receipt"
    audit_path = run_dir / f"{seed}.starts.jsonl"
    if receipt_path.exists():
        return str(receipt_path)
    if raw_path.exists():
        # Raw is the authoritative completion marker. Recover without rerunning.
        raise RuntimeError(f"raw exists without receipt; recover with run.py --recover: {raw_path}")
    if audit_path.exists():
        # Preserve an interrupted attempt before retrying an uncompleted execution.
        audit_path.rename(audit_path.with_name(f"{seed}.interrupted-{time.time_ns()}.jsonl"))
    temp_dir = run_dir / f"{seed}.temp"
    temp_dir.mkdir(exist_ok=True)
    os.environ.update(
        REDRAW_CONDITION=condition, REDRAW_SEED=str(seed), REDRAW_AUDIT_PATH=str(audit_path),
        TMPDIR=str(temp_dir), TMP=str(temp_dir), TEMP=str(temp_dir),
        PYTHONPATH=os.pathsep.join([str(HERE / "hook"), str(ROOT / "src"), str(ROOT)]),
    )
    # Each pool process performs one task at a time; no environment races.
    import tempfile
    tempfile.tempdir = str(temp_dir)
    research._redraw_original_pin = research._pin_process
    research._pin_process = portable_pin
    start_load = loadavg()
    maxima = start_load.copy() if start_load else None
    samples = 1 if maxima else 0
    stop = threading.Event()

    def sample():
        nonlocal maxima, samples
        while not stop.wait(0.25):
            value = loadavg()
            if value is not None:
                maxima = value if maxima is None else [max(a, b) for a, b in zip(maxima, value)]
                samples += 1

    watcher = threading.Thread(target=sample, daemon=True)
    watcher.start()
    started = time.time()
    error = None
    try:
        research._run_one(record, seed, campaign, cpu)
    except Exception:
        error = traceback.format_exc()
        if not raw_path.exists():
            research._atomic_json(raw_path, {
                "schema_version": 2, "case_id": identifier, "seed": seed,
                "problem_hash": research._sha256_bytes(research._canonical_json(record.dsl).encode()),
                "source_hash": research._source_hash(),
                "dependency_lock_hash": research._dependency_hash(),
                "config": {"time_limit_seconds": 180, "cores": 1,
                           "thread_environment": research.THREAD_ENVIRONMENT},
                "execution_contract_issues": ["runner_exception"],
                "process": {"returncode": -1, "timed_out": False,
                            "elapsed_seconds": time.time() - started, "stderr": error},
                "solver_result": None,
            })
    finally:
        stop.set()
        watcher.join()
        research._pin_process = research._redraw_original_pin
    raw = read_json(raw_path)
    receipt = dict(id=identifier, seed=seed, condition=condition, ordinal=ordinal,
                   started_unix=started, finished_unix=time.time(),
                   hostname=socket.gethostname(), cpu=cpu,
                   affinity_supported=raw.get("process", {}).get("actual_affinity") is not None,
                   start_loadavg=start_load, max_loadavg=maxima, load_samples=samples,
                   load_sample_interval_seconds=0.25, runner_error=error,
                   audit=summarize_audit(audit_path, condition))
    research._atomic_json(receipt_path, receipt)
    return str(receipt_path)


def preflight(jobs, smoke):
    from geosolver.runtime.integrity import verify_engine_lock
    identity = research.runtime_fingerprint()
    valid, detail = verify_engine_lock()
    if not valid or identity["source_hash"] != FROZEN_HASH or identity["issues"]:
        raise RuntimeError(f"frozen runtime mismatch: {detail}; {identity}")
    for path, expected in FIXED_INPUT_HASHES.items():
        if sha(path) != expected:
            raise RuntimeError(f"fixed preregistration/predictions changed: {path}")
    rows = prediction_rows()
    ids = list(SMOKE_IDS) if smoke else [r["id"] for r in rows]
    records = {r.identifier: r for r in research._load_cases()}
    for identifier in ids:
        if not records[identifier].runnable or records[identifier].truth_status != "verified":
            raise ValueError(f"not runnable/verified: {identifier}")
    return identity, ids, cpus_for_jobs(jobs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true", help="3 problems, seed 101, both conditions")
    mode.add_argument("--full", action="store_true", help="Windows PC only: all 900 runs")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--recover", action="store_true", help="compatibility flag: raw files are always recovered without rerunning")
    args = parser.parse_args()
    if args.smoke and not 1 <= args.jobs <= 2:
        parser.error("smoke requires --jobs 1 or 2")
    if args.full and args.jobs != 6:
        parser.error("the fixed full campaign requires --jobs 6")
    destination = HERE / "smoke" if args.smoke else HERE
    if args.check_only:
        execute(args, destination)
    else:
        with campaign_lock(destination):
            execute(args, destination)


def execute(args, destination):
    identity, ids, cpus = preflight(args.jobs, args.smoke)
    seeds = [101] if args.smoke else [101, 102, 103]
    fixed = dict(mode="smoke" if args.smoke else "full", ids=ids, seeds=seeds,
                 conditions=list(CONDITIONS), jobs=args.jobs, cpus=cpus,
                 hostname=socket.gethostname(), platform=platform.platform(),
                 runtime=identity, time_limit_seconds=180, cores=1,
                 bootstrap_seed=102304, bootstrap_replicates=10000,
                 inputs={str(p.relative_to(ROOT)): sha(p) for p in
                         [PREDICTIONS, PREREG, ROOT / "benchmarks/research_runner.py",
                          HERE / "run.py", HERE / "aggregate.py",
                          HERE / "hook/sitecustomize.py", HERE / "hook/redraw_patch.py"]})
    selected_records = [r for r in research._load_cases() if r.identifier in ids]
    # Freeze both the corpus references and the exact on-disk DSL used by the CLI.
    fixed["cases"] = [{"id": r.identifier, "dsl": sha(r.dsl_path),
                       "record": hashlib.sha256(research._canonical_json(
                           {"dsl": r.dsl, "references": r.references,
                            "truth_status": r.truth_status}).encode()).hexdigest()}
                      for r in selected_records]
    manifest_path = destination / "manifest.json"
    if manifest_path.exists() and read_json(manifest_path)["fixed"] != fixed:
        raise RuntimeError("resume refused: machine, jobs, runtime, inputs, or design changed")
    print(f"preflight OK: {len(ids) * len(seeds) * 2} runs, {args.jobs} jobs; "
          f"worst solver time {len(ids) * len(seeds) * 2 * 180 / args.jobs / 3600:.2f} h", flush=True)
    if args.check_only:
        return
    destination.mkdir(parents=True, exist_ok=True)
    if not manifest_path.exists():
        manifest = research._manifest(selected_records, seeds)
        for condition in CONDITIONS:
            research._atomic_json(destination / condition / "campaign-manifest.json", manifest)
        research._atomic_json(manifest_path, {"fixed": fixed, "created_unix": time.time()})
    pairs = [(identifier, seed) for identifier in ids for seed in seeds]
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for offset in range(0, len(pairs), args.jobs):
            # A barrier between waves gives equal slots/CPUs to both conditions.
            batch = pairs[offset:offset + args.jobs]
            for condition in CONDITIONS:
                futures = []
                for slot, (identifier, seed) in enumerate(batch):
                    run_dir = destination / condition / "runs" / identifier
                    receipt = run_dir / f"{seed}.receipt"
                    raw = run_dir / f"{seed}.json"
                    if receipt.exists():
                        if not raw.exists():
                            raise RuntimeError(f"completed receipt lacks raw: {receipt}")
                        print(f"skip {condition} {identifier} {seed}", flush=True)
                        continue
                    if raw.exists():
                        research._atomic_json(receipt, dict(
                            id=identifier, seed=seed, condition=condition, recovered=True,
                            runner_error="interrupted after raw commit; load samples unavailable",
                            audit=summarize_audit(run_dir / f"{seed}.starts.jsonl", condition)))
                        print(f"recovered {raw}", flush=True)
                        continue
                    ordinal = (offset // args.jobs) * 2 + CONDITIONS.index(condition)
                    futures.append(pool.submit(run_one, (identifier, seed, condition,
                                                         str(destination), cpus[slot], ordinal)))
                for future in futures:
                    print(f"done {future.result()}", flush=True)
    # Official reference assessor: exactly the historical set-equality scoring.
    for condition in CONDITIONS:
        try:
            research.assess_campaign(destination / condition)
        except Exception:
            # Preserve official-assessor failures, but still count every raw run
            # in our error-aware export instead of losing the campaign summary.
            (destination / condition / "assessment-error.txt").write_text(
                traceback.format_exc(), encoding="utf-8")
    from aggregate import export_per_run, aggregate
    export_per_run(destination)
    aggregate(destination)


if __name__ == "__main__":
    main()
