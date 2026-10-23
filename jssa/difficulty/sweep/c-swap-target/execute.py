"""Run the unchanged public solver; capture its ordinary worker artifact after return."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import os
import subprocess
import threading
import time
import traceback

from common import *


def child(index, cpu):
    assert BASE.is_relative_to(ROOT), 'Run the copied harness inside the clean checkout.'
    os.sched_setaffinity(0, {cpu})
    source = verify_source()
    from geosolver import solve
    from geosolver.engine.runner import EngineRunner

    class CaptureRunner(EngineRunner):
        execution = None

        def run(self, *args, **kwargs):
            self.execution = super().run(*args, **kwargs)
            return self.execution

    job = read(BASE / 'schedule.json')[index]
    output = RAW / 'runs' / f'{index:03d}'
    output.mkdir(parents=True, exist_ok=False)
    runner = CaptureRunner(memory_limit_bytes=3 * 1024**3)
    started = time.monotonic()
    record = {'job': job, 'source': source, 'started_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'cpu': cpu, 'loadavg_start': os.getloadavg()}
    try:
        dsl = read(BASE / job['input'])
        expected = next(c for c in read(BASE / 'selection.json')['cases'] if c['id'] == job['id'])['variants'][job['kind']]['dsl_sha256']
        assert digest(dsl) == expected
        result = solve(dsl, {'time_limit_seconds': job['time_limit_seconds'], 'cores': 1, 'seed': job['seed']}, runner=runner)
        record['result'] = result.model_dump(mode='json')
        assert record['result']['engine']['source_hash'] == SOURCE
        if runner.execution is not None:
            artifact = runner.execution.artifact.model_dump(mode='json')
            save(output / 'artifact.json', artifact)
            (output / 'stdout.log').write_text(runner.execution.stdout)
            (output / 'stderr.log').write_text(runner.execution.stderr)
            actual = artifact.get('process_info', {}).get('import_root')
            record['worker_import_root'] = actual
            record['worker_import_matches'] = actual == str(ROOT / 'src/geosolver') if actual else None
            if actual:
                assert record['worker_import_matches']
    except BaseException as exc:
        record['harness_error'] = repr(exc)
        record['traceback'] = traceback.format_exc()
    record['wall_seconds'] = time.monotonic() - started
    record['loadavg_end'] = os.getloadavg()
    save(output / 'receipt.json', record)
    print(json.dumps({'index': index, 'id': job['id'], 'kind': job['kind'], 'seed': job['seed'],
                      'status': record.get('result', {}).get('status', 'harness_error'),
                      'seconds': round(record['wall_seconds'], 3)}, ensure_ascii=False), flush=True)


def controller(limit=None):
    assert BASE.is_relative_to(ROOT), 'Run the copied harness inside the clean checkout.'
    verify_source()
    jobs = read(BASE / 'schedule.json')
    cpus = read(BASE / 'selection.json')['cpus'][-2:]
    assert len(cpus) <= 2
    RAW.mkdir(parents=True, exist_ok=True)
    pending = [j for j in jobs if not (RAW / 'runs' / f'{j["index"]:03d}' / 'receipt.json').exists()]
    # A partial run is not silently retried.
    assert all(not (RAW / 'runs' / f'{j["index"]:03d}').exists() for j in pending), 'Incomplete run must be recorded as failure, not replaced.'
    if limit is not None:
        pending = pending[:limit]
    save(RAW / f'launch-{int(time.time())}.json', {'pending': [j['index'] for j in pending],
          'script_sha256': sha(__file__), 'source_hash': SOURCE, 'cpus': cpus,
          'selection_sha256': sha(BASE / 'selection.json'), 'schedule_sha256': sha(BASE / 'schedule.json')})

    def lane(lane_index):
        for job in pending[lane_index::len(cpus)]:
            index = job['index']
            cp = subprocess.run([str(PYTHON), '-B', str(BASE / 'execute.py'), 'child', str(index), str(cpus[lane_index])],
                                cwd=ROOT, env=environment(), capture_output=True, text=True)
            print(cp.stdout.strip() or json.dumps({'index': index, 'exit_code': cp.returncode, 'stderr': cp.stderr[-1500:]}), flush=True)
            if cp.returncode or not (RAW / 'runs' / f'{index:03d}/receipt.json').exists():
                save(RAW / 'runs' / f'{index:03d}/receipt.json', {'job': job, 'harness_error': 'child process failed', 'exit_code': cp.returncode, 'stderr': cp.stderr[-3000:]})
    stop_load = threading.Event()

    def load_monitor():
        with (RAW / 'loadavg.jsonl').open('a') as stream:
            while not stop_load.is_set():
                stream.write(json.dumps({'utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                                         'loadavg': os.getloadavg()}) + '\n')
                stream.flush()
                stop_load.wait(30)

    monitor = threading.Thread(target=load_monitor, daemon=True)
    monitor.start()
    try:
        with ThreadPoolExecutor(max_workers=len(cpus)) as pool:
            futures = [pool.submit(lane, i) for i in range(len(cpus))]
            for f in as_completed(futures):
                f.result()
    finally:
        stop_load.set()
        monitor.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['run', 'child'])
    parser.add_argument('args', nargs='*', type=int)
    opts = parser.parse_args()
    if opts.mode == 'child':
        child(*opts.args)
    else:
        controller(opts.args[0] if opts.args else None)
