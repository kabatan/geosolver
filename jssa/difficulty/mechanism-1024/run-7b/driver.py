"""One fixed, non-resumable 648-run campaign. Never retries a solve."""
import csv
import gzip
import hashlib
import json
import os
import signal
import struct
import subprocess
import sys
import threading
import time
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue

OUT = Path(__file__).resolve().parent
M = json.loads((OUT / "pre-run-hashes.json").read_text())
SCRATCH = Path(M["scratch"])
sys.path[:0] = [str(Path(M["frozen_grader"]) / "src"), M["frozen_grader"]]
from benchmarks.research_runner import _answer_keys, read_run_outcome

LOCK = threading.Lock()
COMPLETE = 0
ACTIVE = {}
STARTED = time.time()
CPUS = Queue()
for cpu in M["cpus"]:
    CPUS.put(cpu)


def utc():
    return datetime.now(timezone.utc).isoformat()


def progress(state="実行中"):
    text = (f"# 事前登録7b：{state}\n\n更新 UTC: {utc()}\n\n"
            f"完了: {COMPLETE}/648、実行中: {len(ACTIVE)}、並列上限: 16。\n\n"
            f"180秒・1コア、seed 401–403、再試行なし。経過: {(time.time()-STARTED)/60:.1f}分。\n\n"
            f"生記録: `{SCRATCH}`。時刻・時間は他作業の負荷を含む参考値。\n")
    tmp = OUT / "progress.tmp"
    tmp.write_text(text)
    tmp.replace(OUT / "progress.md")


def run(task):
    global COMPLETE
    record, seed, arm, index = task
    cpu = CPUS.get()
    dest = SCRATCH / "runs" / arm / record["case_id"] / str(seed)
    dest.mkdir(parents=True, exist_ok=False)
    row = {"case_id": record["case_id"], "group": record["group"], "seed": seed,
           "arm": arm, "schedule_index": index, "cpu": cpu, "started_utc": utc(),
           "loadavg_start": os.getloadavg()[0]}
    with LOCK:
        ACTIVE[index] = row
        progress()
    started = time.monotonic()
    result = None
    timed_out = False
    returncode = None
    stdout = stderr = ""
    error = None
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith("GEOSOLVER_ABLATE_")}
        env.update(M["thread_environment"])
        env["PYTHONPATH"] = str(OUT / "probe") + ":" + str(Path(M["clean_source"]) / "src")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["SWITCH_PROBE_OUT"] = str(dest / "probe")
        if arm != "BASE":
            env["GEOSOLVER_ABLATE_" + arm] = "1"
        command = ["taskset", "-c", str(cpu), M["python"], str(OUT / "single_run.py"),
                   record["input_copy"], str(dest / "result.json"), str(seed)]
        process = subprocess.Popen(command, cwd=M["clean_source"], env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, errors="replace", start_new_session=True)
        row["pid"] = process.pid
        (dest / "start.json").write_text(json.dumps(row) + "\n")
        try:
            stdout, stderr = process.communicate(timeout=188)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Only this campaign's process group is terminated.
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        returncode = process.returncode
        if (dest / "result.json").exists():
            result = json.loads((dest / "result.json").read_text())
    except Exception as exc:
        error = repr(exc)
    elapsed = time.monotonic() - started
    events = []
    probe_errors = []
    smooth = 0
    for path in sorted(dest.glob("probe.*.counter")):
        smooth += struct.unpack("Q", path.read_bytes())[0]
    for path in sorted(dest.glob("probe.*.jsonl")):
        for line in path.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                probe_errors.append(str(path))
    artifact = (result or {}).get("worker_artifact") or {}
    info = artifact.get("process_info") or {}
    identity = artifact.get("execution_identity") or {}
    issues = []
    if artifact:
        if identity.get("source_hash") != M["source_hash"]:
            issues.append("source_hash")
        if info.get("cpu_affinity") != [cpu]:
            issues.append("cpu_affinity")
        if not info.get("import_root", "").startswith(M["clean_source"] + "/src/"):
            issues.append("import_root")
    expected_flags = [] if arm == "BASE" else [arm]
    flags = (artifact.get("config_snapshot") or {}).get("ablations")
    if flags is not None and flags != expected_flags:
        issues.append("ablations")
    raw = {**row, "process": {"returncode": returncode, "timed_out": timed_out,
                              "elapsed_seconds": elapsed, "error": error},
           "solver_result": result, "execution_contract_issues": issues,
           "stdout": stdout, "stderr": stderr, "probe_events": events,
           "smooth_calls": smooth, "probe_errors": probe_errors}
    outcome = read_run_outcome(raw)
    actual = _answer_keys(result)
    expected = record["expected_keys"]
    matched = bool(result and outcome["normal_completion"] and actual == expected)
    termination = (result or {}).get("termination_reason")
    if matched:
        category = "correct"
    elif timed_out or termination == "time_limit_reached":
        category = "timeout"
    elif result is None:
        category = "missing"
    elif not actual:
        category = "no_answer"
    elif set(actual) < set(expected):
        category = "partial"
    else:
        category = "wrong"
    handoffs = [e for e in events if e["kind"] in ("main", "added")]
    probe_available = len([e for e in events if e["kind"] == "initialized"]) >= 2
    wall = outcome["wall_seconds"]
    row.update({**outcome, "matched": matched, "category": category, "timed_out": timed_out,
                "returncode": returncode, "elapsed_seconds": elapsed, "wall_seconds": wall,
                "C": wall if matched else 180, "answer_keys": actual, "expected_keys": expected,
                "missing_answers": len(set(expected)-set(actual)), "extra_answers": len(set(actual)-set(expected)),
                "smooth_calls": smooth if probe_available else None,
                "selected_candidates": sum(e["selected"] for e in handoffs) if probe_available else None,
                "handoffs": handoffs, "probe_available": probe_available,
                "execution_contract_issues": issues, "source_hash": identity.get("source_hash"),
                "actual_affinity": info.get("cpu_affinity"), "ablations": flags,
                "ended_utc": utc(), "error": error})
    raw["assessment"] = row
    payload = json.dumps(raw, ensure_ascii=False).encode()
    raw_path = dest / "raw.json.gz"
    with raw_path.open("wb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", mtime=0) as stream:
            stream.write(payload)
    row["raw_path"] = str(raw_path)
    row["raw_sha256"] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    # Full result remains losslessly inside raw.json.gz; avoid duplicate large files.
    if (dest / "result.json").exists():
        (dest / "result.json").unlink()
    (dest / "record.json").write_text(json.dumps(row, ensure_ascii=False) + "\n")
    with LOCK:
        COMPLETE += 1
        ACTIVE.pop(index)
        progress()
        print(f"{utc()} {COMPLETE}/648 {record['case_id']} {seed} {arm} {category} {elapsed:.2f}s", flush=True)
    CPUS.put(cpu)


def main():
    for path, expected in M["files"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, path
    marker = SCRATCH / "campaign-started.json"
    with marker.open("x") as stream:
        json.dump({"started_utc": utc(), "pid": os.getpid()}, stream)
    tasks = []
    for seed in M["seeds"]:
        for record in M["inputs"]:
            k = (zlib.crc32(record["case_id"].encode()) + seed) % 3
            for arm in M["arms"][k:] + M["arms"][:k]:
                tasks.append((record, seed, arm, len(tasks)))
    assert len(tasks) == 648
    (OUT / "schedule.json").write_text(json.dumps([
        {"index": t[3], "case_id": t[0]["case_id"], "seed": t[1], "arm": t[2]}
        for t in tasks], indent=1) + "\n")
    with ThreadPoolExecutor(max_workers=16) as pool:
        for _ in pool.map(run, tasks):
            pass
    progress("実行終了・集計中")
    subprocess.run([M["python"], str(OUT / "analyze.py")], check=True)
    progress("完了")


if __name__ == "__main__":
    main()
