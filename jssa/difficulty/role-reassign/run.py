"""Paired full production solves, max eight, same-time B/R with alternating CPUs."""
from common import *
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import fcntl
import multiprocessing
import os
from queue import Queue
import resource
import tempfile
import threading
import time
import traceback
import zlib
import base64


def run_one(identifier, mode, cpu, ordinal, destination):
    from benchmarks import research_runner as research
    dest = Path(destination)
    campaign = dest / mode
    run_dir = campaign / "runs" / identifier
    run_dir.mkdir(parents=True, exist_ok=True)
    receipt_path, raw_path = run_dir / "0.receipt.json", run_dir / "0.json"
    if receipt_path.exists():
        return read(receipt_path), zlib.compress(json.dumps(read(raw_path)).encode(), 1)
    if raw_path.exists():
        raise RuntimeError(f"orphan raw: {raw_path}")
    audit_path = run_dir / "0.audit.jsonl"
    temporary = run_dir / "temp"
    temporary.mkdir(exist_ok=True)
    # Every solve and its children inherit the same per-file cap and local temp dir.
    resource.setrlimit(resource.RLIMIT_FSIZE, (20_000_000, 20_000_000))
    os.environ.update(research.THREAD_ENVIRONMENT)
    for key in list(os.environ):
        if key.startswith(("GEOSOLVER_ABLATE_", "REDRAW_")) or key == "LM_FIRST":
            os.environ.pop(key)
    os.environ.update(PYTHONDONTWRITEBYTECODE="1", ROLE_CONDITION=mode,
                      ROLE_AUDIT_PATH=str(audit_path),
                      PYTHONPATH=os.pathsep.join([str(HERE / "hook"), str(ROOT / "src"), str(ROOT)]),
                      TMPDIR=str(temporary), TMP=str(temporary), TEMP=str(temporary))
    tempfile.tempdir = str(temporary)
    record = next(c for c in research._load_cases() if c.identifier == identifier)
    start, load = time.time(), os.getloadavg()
    error = None
    try:
        from transport import execute
        raw = execute(record,cpu)
    except Exception:
        error = traceback.format_exc()
        raw = dict(case_id=identifier, seed=0,
                   execution_contract_issues=["runner_exception"],
                   process=dict(returncode=-1, timed_out=False, elapsed_seconds=time.time()-start, stderr=error),
                   solver_result=None)
    receipt = dict(id=identifier, mode=mode, ordinal=ordinal, cpu=cpu,
                   started_unix=start, finished_unix=time.time(), start_loadavg=load,
                   end_loadavg=os.getloadavg(), runner_error=error, audit=audit_summary(audit_path,raw))
    receipt["storage_error"] = None
    try:
        dump(raw_path, raw)
        dump(receipt_path, receipt)
    except OSError:
        # The full return still reaches the owning parent over multiprocessing.
        receipt["storage_error"] = traceback.format_exc()
    return receipt, zlib.compress(json.dumps(raw).encode(), 1)


def main():
    lock = verify_lock()
    for mode in ("B", "R"):
        assert read(HERE / f"preflight-{mode}.json")["all_passed"]
    dest = HERE / "campaign"
    dest.mkdir(exist_ok=True)
    guard = (dest / "runner.lock").open("a+")
    fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest = read(HERE / "manifest.json")
    cpus = lock["cpus"]
    assert len(cpus) == 8 and len(set(cpus)) == 8
    state_lock = threading.Lock()
    retained = {}
    state = dict(started_utc=now(), started_unix=time.time(), completed_pairs=0,
                 planned_pairs=323, completed_runs=0, active={}, stopped=False)
    tasks = Queue()
    for row in manifest:
        tasks.put(row)
    stop = threading.Event()
    bad_consecutive = [0]
    monitor_stop = threading.Event()
    report_requested = threading.Event()

    def log(value):
        line = json.dumps(value, ensure_ascii=False)
        with (HERE / "run.log").open("a") as log_stream:
            log_stream.write(line + "\n")
        print(line, flush=True)

    def controls():
        for command in sys.stdin:
            command = command.strip()
            if command == "stop":
                stop.set()
                with state_lock:
                    state["stopped"] = True
                    save_state()
                log(dict(event="stop_requested", utc=now()))
            elif command == "report":
                report_requested.set()
            elif command == "status":
                with state_lock:
                    log(dict(event="status", **state))

    def monitor():
        from report import main as summarize
        last = time.monotonic()
        while not monitor_stop.wait(1):
            if report_requested.is_set() or time.monotonic() - last >= 60:
                report_requested.clear()
                try:
                    with state_lock:
                        snapshot = dict(retained)
                    summarize(snapshot)
                except Exception:
                    log(dict(event="report_error", traceback=traceback.format_exc()))
                last = time.monotonic()

    threading.Thread(target=controls, daemon=True).start()
    observer = threading.Thread(target=monitor, daemon=True)
    observer.start()

    def save_state():
        dump(HERE / "progress.json", dict(state, updated_utc=now()))

    # Spawn avoids forking a process from a scheduling thread.
    with ProcessPoolExecutor(max_workers=8, mp_context=multiprocessing.get_context("spawn")) as pool:
        def lane(number):
            while not stop.is_set():
                try:
                    row = tasks.get_nowait()
                except Exception:
                    return
                modes = ("B", "R") if row["first"] == "B" else ("R", "B")
                with state_lock:
                    state["active"][str(number)] = dict(id=row["id"], start_unix=time.time())
                    save_state()
                futures = [pool.submit(run_one, row["id"], m, cpus[2*number+i], row["ordinal"], str(dest))
                           for i,m in enumerate(modes)]
                outputs = [f.result() for f in futures]
                receipts = [r for r,_ in outputs]
                with state_lock:
                    for receipt, compressed in outputs:
                        retained[(receipt["id"],receipt["mode"])] = (receipt,compressed)
                    state["completed_pairs"] += 1
                    state["completed_runs"] += 2
                    state["active"].pop(str(number), None)
                    for r in receipts:
                        bad = not r["audit"]["verified"] or bool(r["runner_error"])
                        bad_consecutive[0] = bad_consecutive[0]+1 if bad else 0
                        if bad_consecutive[0] >= 3 or not r["audit"]["final_evaluator_unchanged"]:
                            state["stopped"] = True
                            stop.set()
                    save_state()
                    log(dict(done=state["completed_pairs"], id=row["id"],
                             elapsed=round(time.time()-state["started_unix"],1),
                             audit_ok=[r["audit"]["verified"] for r in receipts]))
        with ThreadPoolExecutor(max_workers=4) as lanes:
            jobs = [lanes.submit(lane,i) for i in range(4)]
            for f in as_completed(jobs):
                f.result()
    monitor_stop.set()
    observer.join()
    verify_lock()
    # Small independent return bundles retain bytes as well as final JSON files.
    chunk, chunk_bytes, chunk_index = [], 0, 0
    for (identifier,mode),(receipt,compressed) in sorted(retained.items()):
        if chunk and chunk_bytes + len(compressed) > 8_000_000:
            dump(HERE/"return-bundles"/f"{chunk_index:03}.json",chunk)
            chunk,chunk_bytes,chunk_index = [],0,chunk_index+1
        chunk.append(dict(id=identifier,mode=mode,receipt=receipt,
                          zlib_base64=base64.b64encode(compressed).decode()))
        chunk_bytes += len(compressed)
    if chunk:
        dump(HERE/"return-bundles"/f"{chunk_index:03}.json",chunk)
    # Restore the authoritative in-memory return from every completed solve.
    # No solver is rerun and no outcome is selected during this recovery.
    restored = []
    for (identifier,mode),(receipt,compressed) in retained.items():
        directory = dest/mode/"runs"/identifier
        raw = json.loads(zlib.decompress(compressed))
        missing = not (directory/"0.json").exists() or not (directory/"0.receipt.json").exists()
        dump(directory/"0.json",raw)
        dump(directory/"0.receipt.json",receipt)
        if missing:
            restored.append(dict(id=identifier,mode=mode))
    dump(HERE/"artifact-recovery.json",dict(utc=now(),retained=len(retained),restored_missing=restored))
    state.update(finished_utc=now(), wall_seconds=time.time()-state["started_unix"])
    save_state()
    dump(HERE / "completion.json", state)
    from report import main as summarize
    summarize(retained)

if __name__ == "__main__":
    main()
