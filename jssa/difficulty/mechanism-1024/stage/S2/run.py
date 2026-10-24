"""Two bounded asynchronous workers, one immutable attempt per phase."""
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

OUT = Path(__file__).resolve().parent
MAN = json.loads((OUT / 'pre-run-hashes.json').read_text())
SCHEDULE = json.loads((OUT / 'schedule.json').read_text())
CONDITIONS = ['a_120', 'a_250', 'a_500', 'b_100000000', 'b_100000000000000', 'b_1000000000000000000000']
LOCK = threading.Lock()
COMPLETED = 0


def now():
    return datetime.now(timezone.utc).isoformat()


def log(message):
    with LOCK:
        with (OUT / 'progress.md').open('a') as f:
            f.write(f'\n- {now()} {message}\n')
        print(message, flush=True)


def launch(phase, key, cpu, condition=None):
    folder = OUT / 'raw' / key
    folder.mkdir(parents=True, exist_ok=True)
    name = 'refined' if phase == 'refine' else condition
    path = folder / (name + '.json')
    with (folder / (name + '.scheduled.json')).open('x') as f:
        json.dump(dict(utc=now(), phase=phase, cpu=cpu, key=key, condition=condition), f)
    cmd = [MAN['python'], str(OUT / 'worker.py'), phase, key, str(cpu)]
    if condition:
        cmd.append(condition)
    env = os.environ | MAN['threads'] | {'PYTHONPATH': MAN['frozen_source'], 'PYTHONDONTWRITEBYTECODE': '1'}
    start = time.monotonic()
    try:
        cp = subprocess.run(cmd, env=env, cwd=OUT, capture_output=True, text=True, timeout=188)
        if cp.returncode or not path.exists():
            error = dict(status='worker_failure', outcome='欠測', achieved_digits=0, returncode=cp.returncode,
                         exception=cp.stderr[-8000:], wall_seconds=time.monotonic()-start)
        else:
            return json.loads(path.read_text())
    except subprocess.TimeoutExpired:
        error = dict(status='timeout', outcome='欠測', achieved_digits=0, exception='outer 188-second limit',
                     wall_seconds=time.monotonic()-start)
    if not path.exists():
        path.write_text(json.dumps(error, ensure_ascii=False, indent=2) + '\n')
    return error


def problem(slot, item):
    global COMPLETED
    key = item['key']
    cpu = MAN['cpus'][slot]
    log(f'{key} 精密化開始（CPU {cpu}、1回のみ）')
    refined = launch('refine', key, cpu)
    log(f'{key} 精密化 {refined.get("status")}、到達 {refined.get("achieved_digits", 0)}桁')
    k = item['order_rotation']
    for cond in CONDITIONS[k:]+CONDITIONS[:k]:
        result = launch('identify', key, cpu, cond)
        log(f'{key} {cond}: {result.get("outcome")}、PSLQ秒={result.get("seconds")}')
    with LOCK:
        COMPLETED += 1
        count = COMPLETED
    log(f'完了 {count}/13件（各6条件）')


def slot_run(slot):
    for item in SCHEDULE[slot::2]:
        problem(slot, item)


if __name__ == '__main__':
    # Check all bytes before the first experimental call; no product mutations.
    for p, expected in MAN['files'].items():
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == expected, p
    source = Path(MAN['frozen_source']).parent
    for p, expected in MAN['source_files'].items():
        assert hashlib.sha256((source / p).read_bytes()).hexdigest() == expected, p
    with (OUT / 'run-started.json').open('x') as f:
        json.dump(dict(utc=now(), pid=os.getpid(), parallelism=2, cpus=MAN['cpus'], loadavg=os.getloadavg()), f)
    log('固定ハッシュ全件一致。並列2・各1 CPUで開始。')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for result in concurrent.futures.as_completed([pool.submit(slot_run, i) for i in range(2)]):
            result.result()
    (OUT / 'run-finished.json').write_text(json.dumps(dict(utc=now(), completed=COMPLETED, loadavg=os.getloadavg()))+'\n')
    log('13件・78条件の一度ずつの実行終了。保存結果から集計。')
    subprocess.run([sys.executable, str(OUT / 'report.py')], check=True)
