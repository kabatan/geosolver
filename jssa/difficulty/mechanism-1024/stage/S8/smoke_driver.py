"""Only the 24 pre-fixed 20-second smoke jobs; cannot execute the main plan."""
import concurrent.futures
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path
from queue import Queue

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SOURCE = Path('/tmp/mechanism-7b-lkdjle5l/final')
PYTHON = Path('/home/kabatan/work/solver/.venv/bin/python')

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(path, data):
    with path.open('x') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def main():
    assert len(sys.argv) == 2 and sys.argv[1] == 'run-smoke', 'Explicit run-smoke required'
    plan = json.loads((HERE / 'smoke-plan.json').read_text())
    configs = json.loads((HERE / 'configs.json').read_text())
    assert len(plan['jobs']) == 24 and plan['seed'] == 601
    assert plan['time_limit_seconds'] == 20 and plan['max_parallel'] == 6
    root = HERE / 'smoke'
    root.mkdir()  # no accidental rerun/overwrite
    cpus = Queue()
    selected = sorted(os.sched_getaffinity(0))[:6]
    for cpu in selected:
        cpus.put(cpu)
    assert len(selected) == 6
    save(root / 'freeze.json', dict(platform=platform.platform(), host=platform.node(),
        python=str(PYTHON), python_sha256=sha(PYTHON.resolve()), cpus=selected,
        files_sha256={p.relative_to(HERE).as_posix(): sha(p) for p in
            [HERE / 'smoke-plan.json', HERE / 'configs.json', HERE / 'smoke_driver.py',
             HERE / 'smoke_worker.py', HERE / 'observe/sitecustomize.py']}))
    byname = {c['name']: c for c in configs['configurations']}

    def run(job):
        cpu = cpus.get()
        try:
            dest = root / f"{job['index']:02d}"
            dest.mkdir()
            assert sha(REPO / job['dsl_path']) == job['input_sha256']
            env = {k: v for k, v in os.environ.items() if not k.startswith(('GEOSOLVER_', 'S8_'))}
            env.update(configs['thread_environment'])
            env.update(byname[job['configuration']]['environment'])
            env.update(PYTHONPATH=str(HERE / 'observe') + ':' + str(SOURCE / 'src'),
                PYTHONDONTWRITEBYTECODE='1', S8_SOURCE_ROOT=str(SOURCE),
                S8_SMOKE_TRACE=str(dest / 'trace'))
            cmd = ['/usr/bin/taskset', '-c', str(cpu), str(PYTHON), '-B',
                   str(HERE / 'smoke_worker.py'), str(REPO / job['dsl_path']), str(dest / 'worker.json')]
            save(dest / 'start.json', dict(**job, cpu=cpu, command=cmd,
                environment={k: v for k, v in env.items() if k.startswith(('GEOSOLVER_', 'S8_'))
                             or k in configs['thread_environment'] or k == 'PYTHONPATH'}))
            t0 = time.monotonic()
            proc = subprocess.Popen(cmd, env=env, cwd=REPO, start_new_session=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            timed_out = False
            try:
                stdout, stderr = proc.communicate(timeout=28)
            except subprocess.TimeoutExpired:
                timed_out = True
                # Kill owned descendants even if EngineRunner starts a new session.
                import psutil
                try:
                    children = psutil.Process(proc.pid).children(recursive=True)
                except psutil.Error:
                    children = []
                for child in reversed(children):
                    try:
                        child.kill()
                    except psutil.Error:
                        pass
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
            # Infrastructure diagnostics only; solver answers never printed by worker.
            (dest / 'stderr.log').write_bytes(stderr)
            save(dest / 'end.json', dict(returncode=proc.returncode, outer_timeout=timed_out,
                elapsed_seconds=time.monotonic() - t0, stdout_bytes=len(stdout), stderr_bytes=len(stderr)))
            print(f"smoke {job['index']:02d} {job['configuration']} {job['case_id']} rc={proc.returncode} timeout={timed_out}", flush=True)
            return dict(**job, returncode=proc.returncode, outer_timeout=timed_out,
                        worker_receipt=(dest / 'worker.json').exists())
        finally:
            cpus.put(cpu)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(run, plan['jobs']))
    save(root / 'execution.json', dict(jobs=results, planned=24, executed=len(results),
        max_parallel=6, correctness_recorded=False, main_measurement_executed=False))

if __name__ == '__main__':
    main()
