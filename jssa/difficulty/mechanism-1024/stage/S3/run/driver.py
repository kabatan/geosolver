"""Detached no-retry campaign with two fixed single-core streams and auto-analysis."""
import concurrent.futures
import hashlib
import json
import os
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
M = json.loads((OUT / "pre-run-hashes.json").read_text())
ROOT = Path(M["scratch"])
LOCK, EVENTS, STOP = threading.Lock(), [], threading.Event()


def event(**kw):
    with LOCK:
        row = dict(utc=datetime.now(timezone.utc).isoformat(), loadavg=list(os.getloadavg()), **kw)
        EVENTS.append(row)
        with (ROOT / "events.jsonl").open("a") as f:
            f.write(json.dumps(row)+"\n")
        done = sum(e.get("stage") == "problem_done" for e in EVENTS)
        lines = ["# S3 進捗", "", f"完了 {done}/12問。2並列、各1コア、内部スレッド1。", f"生データ: `{ROOT}`", "", "```"]
        lines += [f"{e['utc']} {e.get('case_id', '')} {e['stage']} {e.get('arm', '')} {e.get('returncode', '')}" for e in EVENTS if e["stage"] != "load_sample"]
        lines += ["```", ""]
        temp = OUT / "progress.md.tmp"
        temp.write_text("\n".join(lines))
        temp.replace(OUT / "progress.md")


def stage(task, cpu, mode, arm=None):
    case = task["case_id"]
    d = ROOT / "runs" / case
    env = {k: v for k, v in os.environ.items() if not k.startswith("GEOSOLVER_ABLATE_") and k != "GEOSOLVER_S3_TANGENCY_MODE"}
    env.update(M["thread_environment"])
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", PYTHONHASHSEED="0")
    env["PYTHONPATH"] = M["frozen_origin" if mode in ("verify", "references") else "source_origin"]
    if mode == "refine":
        env["GEOSOLVER_S3_TANGENCY_MODE"] = arm
    cmd = ["taskset", "-c", str(cpu), M["python"], "-B", str(OUT / "worker.py"), str(ROOT), mode, case]
    if arm:
        cmd.append(arm)
    event(case_id=case, stage=mode+"_start", arm=arm, cpu=cpu)
    started = time.monotonic()
    with (d / (mode+("."+arm if arm else "")+".log")).open("w") as log:
        p = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = p.wait(timeout=98 if mode in ("refine", "verify") else 90)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            code = 124
    event(case_id=case, stage=mode+"_end", arm=arm, cpu=cpu, returncode=code, seconds=time.monotonic()-started)
    return code == 0


def stream(tasks, cpu):
    for task in tasks:
        stage(task, cpu, "references")
        for arm in task["arm_order"]:
            if stage(task, cpu, "refine", arm):
                measured = stage(task, cpu, "measure", arm)
                stage(task, cpu, "verify", arm)
                if measured and task["case_id"] == M["trace_case"]:
                    stage(task, cpu, "iterations", arm)
        event(case_id=task["case_id"], stage="problem_done")


def sample_load():
    while not STOP.wait(30):
        event(stage="load_sample")


if __name__ == "__main__":
    assert not (ROOT / "started.json").exists(), "No retries"
    for collection in ("files", "source_files", "s1_saved_inputs"):
        for path, expected in M[collection].items():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, path
    (ROOT / "started.json").write_text(json.dumps(dict(pid=os.getpid(), sid=os.getsid(0), utc=datetime.now(timezone.utc).isoformat())))
    event(stage="campaign_start")
    threading.Thread(target=sample_load, daemon=True).start()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(stream, M["inputs"][i::2], cpu) for i, cpu in enumerate(M["cpus"])]
        for job in jobs:
            job.result()
    STOP.set()
    event(stage="campaign_done")
    subprocess.run([M["python"], "-B", str(OUT / "analyze.py")], check=True)
    event(stage="analysis_done")
    subprocess.run([M["python"], "-B", str(OUT / "audit.py")], check=True)
