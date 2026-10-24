"""Asynchronous campaign, no retries; only two independent single-core streams."""
import concurrent.futures
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
M = json.loads((OUT / "pre-run-hashes.json").read_text())
ROOT = Path(M["scratch"])
LOCK = threading.Lock()
EVENTS = []


def event(**kw):
    with LOCK:
        row = {"utc": datetime.now(timezone.utc).isoformat(), "loadavg": list(os.getloadavg()), **kw}
        EVENTS.append(row)
        with (ROOT / "events.jsonl").open("a") as f:
            f.write(json.dumps(row) + "\n")
        done = sum(e.get("stage") == "problem_done" for e in EVENTS)
        lines = ["# S1 進捗", "", f"完了 {done}/12問。同時実行最大2、1工程1コア、内部スレッド1。", f"生データ: `{ROOT}`", "", "```"]
        lines += [f"{e['utc']} {e.get('case_id', '')} {e['stage']} {e.get('arm', '')} {e.get('returncode', '')}" for e in EVENTS]
        lines += ["```", ""]
        temp = OUT / "progress.md.tmp"
        temp.write_text("\n".join(lines))
        temp.replace(OUT / "progress.md")


def stage(task, cpu, mode, arm=None):
    case = task["case_id"]
    d = ROOT / "runs" / case
    d.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GEOSOLVER_ABLATE_")}
    env.update(M["thread_environment"])
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
    env["PYTHONPATH"] = str(ROOT / ("frozen/src" if mode == "verify" else "final/src"))
    if mode == "refine" and arm == "NO_RESIDUAL_REWRITE":
        env["GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE"] = "1"
    cmd = ["taskset", "-c", str(cpu), M["python"], "-B", str(OUT / "worker.py"), str(ROOT), mode, case]
    if arm:
        cmd.append(arm)
    limit = 180 if mode == "search" else (98 if mode in ("refine", "verify") else 90)
    event(case_id=case, stage=mode + "_start", arm=arm, cpu=cpu)
    started = time.monotonic()
    with (d / (mode + ("." + arm if arm else "") + ".log")).open("w") as log:
        p = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = p.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            code = 124
    event(case_id=case, stage=mode + "_end", arm=arm, cpu=cpu, returncode=code, seconds=time.monotonic()-started)
    return code == 0


def stream(tasks, cpu):
    for task in tasks:
        if stage(task, cpu, "search") and stage(task, cpu, "scales"):
            for arm in task["arm_order"]:
                if stage(task, cpu, "refine", arm):
                    stage(task, cpu, "measure", arm)
                    stage(task, cpu, "verify", arm)
        event(case_id=task["case_id"], stage="problem_done")


if __name__ == "__main__":
    assert not (ROOT / "started.json").exists(), "No reruns"
    for p, expected in M["files"].items():
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == expected, p
    (ROOT / "started.json").write_text(json.dumps({"utc": datetime.now(timezone.utc).isoformat()}))
    event(stage="campaign_start")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(stream, M["inputs"][i::2], cpu) for i, cpu in enumerate(M["cpus"])]
        for job in jobs:
            job.result()
    event(stage="campaign_done")
    subprocess.run([M["python"], "-B", str(OUT / "analyze.py")], check=True)
