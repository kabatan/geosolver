"""At most three isolated numerical streams; resumable without rerunning failures."""
from __future__ import annotations
import argparse
import concurrent.futures
import datetime
import signal
import subprocess
import time
import traceback
from common import *

def worker(job, cpu):
    os.sched_setaffinity(0, {cpu})
    fp = fingerprint()
    started = time.monotonic()
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.runner import EngineRunner
    from geosolver.application.service import solve
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    dsl = read(BASE/job['input'])
    assert sha(dsl) == job['input_hash']
    problem = GeometryProblem.model_validate(dsl)
    document = problem.engine_document()
    bundle = load_problem_bundle(document)
    raw = {'job': job, 'runtime': fp, 'worker_cpu': cpu, 'pid': os.getpid(),
           'variables': list(bundle.var_names), 'input_hash': sha(dsl),
           'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    engine = EngineRunner(memory_limit_bytes=2*1024**3)
    try:
        if job['limit'] >= 180:
            result = solve(problem, {'time_limit_seconds': job['limit'], 'seed': job['seed'], 'cores': 1}, runner=engine)
            raw['solver_result'] = result.model_dump(mode='json')
        else:
            execution = engine.run(document, seed=job['seed'], cores=1,
                                   time_limit_seconds=job['limit'])
            a = execution.artifact
            assert a.execution_identity['source_hash'] == SOURCE
            raw['artifact'] = a.model_dump(mode='json')
            raw['solver_result'] = {'status': 'solved' if a.answers else 'no_answer_found',
                'answers': [x.model_dump(mode='json') for x in a.answers],
                'termination_reason': a.termination_reason,
                'elapsed_seconds': time.monotonic()-started, 'engine': a.execution_identity,
                'diagnostics': {**a.diagnostics, 'candidate_records': a.candidate_records,
                    'phase_timings': a.phase_timings, 'counters': a.counters,
                    'process_info': a.process_info, 'numeric_feasible': a.numeric_feasible,
                    'rejection_tags': a.rejection_tags}}
    except Exception as error:
        raw['solver_result'] = {'status': 'exception', 'answers': [],
            'error': {'type': type(error).__name__, 'code': getattr(error, 'code', None),
                      'message': str(error)}, 'elapsed_seconds': time.monotonic()-started}
        raw['traceback'] = traceback.format_exc()
    raw['wall_seconds'] = time.monotonic()-started
    assert fingerprint()['source_hash'] == SOURCE
    save(EXTERNAL/'runs'/f'{job["key"]}.json', raw)

def choose_cpus():
    import psutil
    samples = [psutil.cpu_percent(interval=0.5, percpu=True) for _ in range(3)]
    eligible = sorted(os.sched_getaffinity(0))
    groups = {}
    for cpu in eligible:
        root = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        key = ((root/'physical_package_id').read_text().strip(), (root/'core_id').read_text().strip())
        groups.setdefault(key, []).append(cpu)
    ranked = sorted(groups.values(), key=lambda cs: sum(samples[k][c] for k in range(3) for c in cs))
    chosen = [min(cs, key=lambda c:sum(s[c] for s in samples)) for cs in ranked[:3]]
    return chosen, samples

def supervise(job, cpu):
    rawpath = EXTERNAL/'runs'/f'{job["key"]}.json'
    if rawpath.exists():
        assert read(rawpath)['job'] == job
        return {'key': job['key'], 'existing': True}
    (EXTERNAL/'logs').mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with (EXTERNAL/'logs'/f'{job["key"]}.log').open('w') as log:
        command = [sys.executable, str(BASE/'run.py'), '--worker', canonical(job), '--cpu', str(cpu)]
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            proc.wait(timeout=job['limit']+25)
            timeout = False
        except subprocess.TimeoutExpired:
            timeout = True
            import psutil
            try: descendants = psutil.Process(proc.pid).children(recursive=True)
            except psutil.Error: descendants = []
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            # EngineRunner starts its own group; kill only our descendants.
            for child in descendants:
                try: child.kill()
                except psutil.Error: pass
            proc.wait()
        if not rawpath.exists():
            save(rawpath, {'job':job, 'runtime': {'source_hash':SOURCE},
                'wall_seconds':time.monotonic()-started, 'returncode':proc.returncode,
                'solver_result':{'status':'external_timeout' if timeout else 'process_crash', 'answers':[]}})
    return {'key': job['key'], 'existing': False, 'wall_seconds': time.monotonic()-started}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker'); parser.add_argument('--cpu', type=int)
    parser.add_argument('--jobs', default=str(BASE/'jobs.json'))
    args = parser.parse_args()
    if args.worker:
        worker(json.loads(args.worker), args.cpu); return
    fp = fingerprint(); manifest = read(BASE/'input-manifest.json')
    assert sha((BASE/'selection.json').read_bytes()) == manifest['selection_sha256']
    assert sha((BASE/'jobs.json').read_bytes()) == manifest['jobs_sha256']
    for path, digest in manifest['files'].items(): assert sha((BASE/path).read_bytes()) == digest
    jobs = read(args.jobs)['jobs']; cpus, samples = choose_cpus()
    stamp = Path(args.jobs).stem
    receipt = {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'runtime':fp,
               'cpus':cpus, 'cpu_samples':samples, 'load':os.getloadavg(), 'max_parallel':3,
               'jobs':len(jobs), 'external':str(EXTERNAL), 'jobs_hash':sha(jobs),
               'wrapper_hashes':{p.name:sha(p.read_bytes()) for p in BASE.glob('*.py')}}
    receipt_path = BASE/f'execution-{stamp}.json'
    assert not receipt_path.exists(), 'Use a new jobs filename for a separate launch receipt.'
    save(receipt_path, receipt)
    started = time.monotonic(); done = 0
    # One sequential lane per core: never assign two streams to the same core.
    lanes = [jobs[i::3] for i in range(3)]
    import threading
    lock = threading.Lock()
    def lane(index):
        nonlocal done
        for job in lanes[index]:
            supervise(job, cpus[index])
            with lock:
                done += 1
                if done % 12 == 0 or done == len(jobs):
                    print(f'completed {done}/{len(jobs)}, wall {time.monotonic()-started:.1f}s', flush=True)
                save(EXTERNAL/f'progress-{stamp}.json', {'completed':done, 'total':len(jobs),
                     'elapsed':time.monotonic()-started, 'last':job['key']})
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(lane, i) for i in range(3)]
        for future in futures: future.result()
    receipt['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt['wall_seconds'] = time.monotonic()-started
    receipt['final_runtime'] = fingerprint(); receipt['completed'] = done
    save(BASE/f'completed-{stamp}.json', receipt)

if __name__ == '__main__': main()
