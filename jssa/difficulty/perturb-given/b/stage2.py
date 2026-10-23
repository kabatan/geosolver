"""Q40b stage 2: immutable preparation and at most two bounded trials per call.

Commands: prepare, batch, status. Every batch finishes within 205 seconds;
each individual trial has the registered 180-second wall/CPU ceilings.
No completion command can repeat a claimed trial.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

from stage2_common import (CLEAN, FROZEN, HERE, OUT, PYTHON, RAW, SOURCE, THREADS,
                          read, sha, utc, write)

ROOT = HERE.parents[3]
PLAN = read(HERE / 'execution-plan.json')['runs']
IMPL = HERE / 'implementation.lock.json'
CODE = ('stage2.py', 'stage2_common.py', 'q40b_worker.py', 'verify_observer.py')
PREDICTION_COMMIT = 'e50c0002dc55b242d13c9edb6ec5f781a45ccda8'


def git(*args, cwd=CLEAN):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def source_check():
    assert git('rev-parse', 'HEAD') == FROZEN
    assert git('status', '--porcelain') == '', 'frozen checkout is not clean'
    manifest = read(HERE / 'shared/source-manifest.json')
    for name, entry in manifest['files'].items():
        assert sha(CLEAN / name) == entry['sha256'], name
    lock = read(HERE / 'prediction.lock.json')
    for name, expected in lock['files_sha256'].items():
        path = CLEAN / name if name.startswith(('src/', 'benchmarks/')) or name in ('pyproject.toml', 'uv.lock') else ROOT / name
        assert sha(path) == expected, 'locked file mismatch: ' + name
    actual = {str(p.relative_to(CLEAN)) for p in (CLEAN / 'src').rglob('*') if p.is_file()}
    assert actual == set(manifest['files']), 'extra/missing source file'
    return {'frozen_commit': FROZEN, 'src_files': len(actual), 'src_tree': git('rev-parse', 'HEAD:src'),
            'all_source_bytes_match': True, 'checkout_clean': True}


def prepare():
    assert not IMPL.exists(), 'implementation already sealed'
    assert read(OUT / 'observer-validation.json')['passed']
    checked = subprocess.run([str(PYTHON), '-B', str(HERE / 'stage1.py'), 'check'],
                             cwd=ROOT, capture_output=True, text=True, check=True)
    source = source_check()
    for name in ('prediction.md', 'prediction.lock.json', 'execution-plan.json'):
        path = str((HERE / name).relative_to(ROOT))
        committed = subprocess.check_output(['git', 'show', PREDICTION_COMMIT + ':' + path], cwd=ROOT)
        assert committed == (HERE / name).read_bytes(), 'prediction commit mismatch'
    import geosolver
    from geosolver.runtime.integrity import engine_identity_hashes, verify_engine_lock
    assert Path(geosolver.__file__).resolve() == CLEAN / 'src/geosolver/__init__.py'
    assert verify_engine_lock() == (True, SOURCE)
    locked = read(CLEAN / 'src/geosolver/dependency-lock.json')['packages']
    versions = {}
    for name, wanted in locked.items():
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            assert name == 'colorama' and sys.platform == 'linux'
            continue
        assert versions[name] == wanted, (name, versions[name], wanted)
    cores = sorted(os.sched_getaffinity(0))[-2:]
    assert len(cores) == 2
    environment = {
        'python': sys.version, 'executable': str(PYTHON), 'python_executable_sha256': sha(PYTHON.resolve()),
        'prefix': sys.prefix, 'platform': platform.platform(), 'uname': list(platform.uname()),
        'dependencies': versions, 'identity': engine_identity_hashes(),
        'dependency_storage': '/home/kabatan/work/solver/.venv/lib/python3.12/site-packages (read only)',
        'isolated_prefix': '/tmp/q40b-env', 'import_root': str(CLEAN / 'src'),
        'thread_environment': dict.fromkeys(THREADS, '1'), 'pythonhashseed': '0',
        'lane_cores': cores, 'maximum_concurrency': 2,
        'load_at_preparation': os.getloadavg(), 'prepared_utc': utc(),
    }
    OUT.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)
    write(OUT / 'environment.json', environment, exclusive=True)
    authorization = {
        'schema': 'q40b-stage2-authorization-v1', 'recorded_utc': utc(),
        'authorization_source': 'User message in this stage-2 task',
        'user_authorized_completed_solver_execution': True,
        'claude_commit_push_confirmation': {'confirmed_by_user_report': True,
            'commit': PREDICTION_COMMIT, 'confirmation_utc': '2026-10-23T18:02:20Z',
            'independently_checked_remote_push': False,
            'locally_verified_commit_and_prediction_bytes': True,
            'commit_metadata': git('show', '-s', '--format=%H %cI %s', PREDICTION_COMMIT, cwd=ROOT)},
        'user_priority': '最優先、2段階運用の段階2',
        'stage1_check': json.loads(checked.stdout), 'frozen_checkout_check': source,
        'prediction_lock_sha256': sha(HERE / 'prediction.lock.json'),
        'sibling_lock_sha256': sha(HERE.parent / 'a/prediction.lock.json'),
        'source_hash': SOURCE,
        'user_overrides': {'maximum_concurrency': 2, 'per_command_max_seconds': 210,
                           'per_trial_load_recording': True},
        'no_input_prediction_or_threshold_changes': True,
        'solver_calls_before_implementation_seal': 0,
    }
    write(OUT / 'authorization-receipt.json', authorization, exclusive=True)
    lock = {
        'schema': 'q40b-implementation-lock-v1', 'sealed_utc': utc(),
        'code_sha256': {name: sha(HERE / name) for name in CODE},
        'prediction_lock_sha256': sha(HERE / 'prediction.lock.json'),
        'environment_sha256': sha(OUT / 'environment.json'),
        'authorization_receipt_sha256': sha(OUT / 'authorization-receipt.json'),
        'observer_validation_sha256': sha(OUT / 'observer-validation.json'),
        'frozen_source': source, 'source_hash': SOURCE, 'lane_cores': cores,
        'schedule': 'block % 2 assigns lane; each lane follows locked run_order; 6 variants stay on same core',
        'entry': 'geosolver.solve with EngineRunner(worker_module=q40b_worker); wrapper calls unchanged frozen worker.main',
        'observation': '_verify_revision original function, first verified=True return; dedicated FirstFigure(BaseException)',
        'stop_boundary': 'jssa observed_pipeline saves figure then rethrows; frozen runtime_session closes and worker serializes stop',
        'identify_monitor': 'both module and assembly aliases guarded; count must be zero',
        'clock_scope': 'worker process_time_ns from first wrapper statements before solver import plus live/reaped child CPU; parent wall before solve/validation',
        'child_cpu_resolution_seconds': 1 / os.sysconf('SC_CLK_TCK'),
        'cpu_cap': 180, 'wall_cap': 180, 'worker_save_reserve_seconds': 2,
        'outer_watchdog_seconds': 195, 'maximum_batch_seconds': 205,
        'raw_log_directory': str(RAW), 'no_retries': True,
        'observer_verification': 'source inspection and synthetic adapter test; no solver trials before lock',
    }
    write(IMPL, lock, exclusive=True)
    print(json.dumps({'prepared': True, 'implementation_sha256': sha(IMPL),
                      'source_hash': SOURCE, 'lane_cores': cores}, ensure_ascii=False))


def locked_check():
    lock = read(IMPL)
    assert lock, 'no implementation seal'
    assert sha(HERE / 'prediction.lock.json') == lock['prediction_lock_sha256']
    assert sha(OUT / 'environment.json') == lock['environment_sha256']
    assert sha(OUT / 'authorization-receipt.json') == lock['authorization_receipt_sha256']
    for name, expected in lock['code_sha256'].items():
        assert sha(HERE / name) == expected, name
    source_check()
    return lock


class WallLimit(BaseException):
    pass


def one(index):
    """Private child command. Only batch may create its exclusive claim."""
    import threading
    import psutil
    import geosolver
    from geosolver.engine import EngineRunner
    from geosolver.runtime.integrity import source_tree_hash
    run = OUT / 'runs' / f'{index:04d}'
    claim = read(run / 'claim.json')
    assert claim and not (run / 'record.json').exists()
    assert claim['run_order'] == index
    os.sched_setaffinity(0, {claim['core']})
    assert Path(geosolver.__file__).resolve() == CLEAN / 'src/geosolver/__init__.py'
    assert source_tree_hash() == SOURCE
    assert sha(HERE / claim['dsl_path']) == claim['dsl_sha256']
    dsl = read(HERE / claim['dsl_path'])
    runner = EngineRunner(worker_module='q40b_worker')
    stop = threading.Event()
    samples = []
    worker_cpu_max = 0.0
    timeout_kind = None
    worker_seen = False

    def monitor():
        nonlocal worker_cpu_max, timeout_kind, worker_seen
        last_load = -1.0
        while not stop.wait(0.1):
            elapsed = (time.perf_counter_ns() - started) / 1e9
            entry = read(run / 'worker-start.json')
            cpu = None
            details = []
            if entry:
                worker_seen = True
                try:
                    root = psutil.Process(entry['pid'])
                    for p in [root, *root.children(recursive=True)]:
                        with p.oneshot():
                            t = p.cpu_times()
                            details.append({'pid': p.pid, 'user_s': t.user, 'system_s': t.system,
                                'reaped_user_s': t.children_user, 'reaped_system_s': t.children_system,
                                'threads': p.num_threads(), 'affinity': p.cpu_affinity()})
                    cpu = sum(d['user_s'] + d['system_s'] + d['reaped_user_s']
                              + d['reaped_system_s'] for d in details) - entry['worker_cpu_start_ns'] / 1e9
                    worker_cpu_max = max(worker_cpu_max, cpu)
                    if cpu >= 180 and not (run / 'figure.json').exists():
                        timeout_kind = 'cpu'
                        write(run / 'limit.json', {'kind': 'cpu', 'elapsed_wall_s': elapsed, 'worker_cpu_s': cpu})
                        runner.cancel()
                except psutil.Error:
                    pass
            if elapsed - last_load >= 1:
                samples.append({'wall_s': elapsed, 'load_average': os.getloadavg(),
                                'worker_tree_cpu_s': cpu, 'processes': details})
                last_load = elapsed

    def alarm(signum, frame):
        nonlocal timeout_kind
        timeout_kind = 'wall'
        raise WallLimit()

    os.environ['Q40B_RUN_DIR'] = str(run)
    os.environ['Q40B_RAW_LOG'] = str(RAW / f'{index:04d}.worker.log')
    started_utc = utc()
    parent_start_ns = time.process_time_ns()
    started = time.perf_counter_ns()
    os.environ['Q40B_OUTER_PERF_NS'] = str(started)
    signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, 180)
    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    result = None
    exception = None
    try:
        result = geosolver.solve(dsl, {'seed': claim['seed'], 'cores': 1, 'time_limit_seconds': 180}, runner=runner)
    except WallLimit:
        write(run / 'limit.json', {'kind': 'wall', 'elapsed_wall_s': (time.perf_counter_ns() - started) / 1e9,
                                  'worker_cpu_s_last_sample': worker_cpu_max})
        runner.cancel()
    except BaseException as exc:
        exception = type(exc).__name__ + ': ' + str(exc)
        runner.cancel()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        finished_ns = time.perf_counter_ns()
        parent_end_ns = time.process_time_ns()
        stop.set()
        watcher.join(timeout=1)
    end = read(run / 'worker-end.json', {})
    ready = read(run / 'observer-ready.json', {})
    fig = read(run / 'figure.json')
    violations = []
    if worker_seen and not ready.get('instrumentation_installed'):
        violations.append('observer_not_ready')
    if (run / 'identify-violation.json').exists() or end.get('identify_calls', 0):
        violations.append('identify_called')
    actual_wall = (finished_ns - started) / 1e9
    actual_cpu = end.get('snapshot', {}).get('cpu_s', worker_cpu_max)
    cpu_quality = 'worker_end_snapshot' if 'snapshot' in end else 'parent_last_sample'
    if fig:
        v = fig['verification']
        from decimal import Decimal
        if (fig['source_hash'] != SOURCE or fig['dsl_hash'] != claim['dsl_sha256']
                or fig['environment_hash'] != claim['environment_hash']
                or fig['run_order'] != index or not fig['candidate_uid']
                or not v['verified'] or not v['hard_feasible']
                or Decimal(v['normalized_residual']) > Decimal('1e-30')
                or v['values'] != fig['verified_coordinates']
                or fig['identify_calls'] != 0):
            violations.append('figure_receipt_invalid')
        if read(run / 'figure-commit.json', {}).get('sha256') != sha(run / 'figure.json'):
            violations.append('figure_receipt_not_committed')
        if fig['affinity'] != [claim['core']]:
            violations.append('unexpected_core_affinity')
        if any(x != '1' for x in fig['thread_environment'].values()):
            violations.append('unexpected_numeric_thread_count')
        if any(c.get('race') for c in fig['discovery']['live_children']):
            violations.append('child_cpu_sampling_race')
        cpu = fig['discovery']['cpu_s']
        wall = fig['wall_s']
        cpu_quality = 'discovery_snapshot'
        if cpu > 180:
            timeout_kind = 'cpu'
        if wall > 180:
            timeout_kind = 'wall'
        success = not violations and cpu <= 180 and wall <= 180
    else:
        cpu, wall, success = actual_cpu, actual_wall, False
    public = result.model_dump(mode='json') if result is not None else None
    if public is not None:
        write(run / 'public-result.json', public)
    if not success and timeout_kind is None and public and public.get('termination_reason') == 'time_limit_reached':
        timeout_kind = 'solver_wall_deadline'
    status = ('success' if success else 'measurement_violation' if violations else
              'timeout' if timeout_kind else 'failure')
    raw = RAW / f'{index:04d}.worker.log'
    record = {**claim, 'group': claim['cohort'], 'status': status, 'success': success,
        'started_utc': started_utc, 'ended_utc': utc(), 'cpu_s': cpu, 'wall_s': wall,
        'cpu_measurement': cpu_quality, 'actual_end_cpu_s': actual_cpu, 'actual_end_wall_s': actual_wall,
        'parent_cpu_s': (parent_end_ns - parent_start_ns) / 1e9,
        'cleanup_s': max(0, actual_wall - wall) if fig else 0,
        'cleanup_worker_cpu_s': max(0, actual_cpu - cpu) if fig else 0,
        'timeout_kind': timeout_kind,
        'candidate_uid': fig.get('candidate_uid') if fig else None,
        'precision_dps': fig['verification']['precision_dps'] if fig else None,
        'normalized_residual': fig['verification']['normalized_residual'] if fig else None,
        'hard_feasible': fig['verification']['hard_feasible'] if fig else False,
        'identify_calls': end.get('identify_calls', ready.get('identify_calls', 0)),
        'source_hash': SOURCE, 'dsl_hash': claim['dsl_sha256'],
        'inferred_bounds': (fig or end).get('inferred_bounds'),
        'bounds_variable_names': (fig or end).get('bounds_variable_names'),
        'receipt_path': str((run / 'figure.json').relative_to(HERE)) if fig else None,
        'figure_sha256': sha(run / 'figure.json') if fig else None,
        'load_average_start': claim['load_average_start'], 'load_average_end': os.getloadavg(),
        'measurement_violations': violations, 'exception': exception,
        'public_status': public.get('status') if public else None,
        'public_termination': public.get('termination_reason') if public else None,
        'raw_log_path': str(raw), 'raw_log_sha256': sha(raw) if raw.exists() else None,
        'raw_log_bytes': raw.stat().st_size if raw.exists() else 0,
        'effective_cores': 1, 'numeric_threads': 1,
    }
    write(run / 'load-and-resources.json', samples, exclusive=True)
    write(run / 'record.json', record, exclusive=True)
    print(json.dumps({k: record[k] for k in ('run_order', 'canonical_id', 'variant', 'seed', 'status', 'cpu_s', 'wall_s', 'measurement_violations')}))


def launch(index, lock):
    row = PLAN[index]
    lane = row['block'] % 2
    run = OUT / 'runs' / f'{index:04d}'
    claim = {**row, 'run_order': index, 'lane': lane, 'core': lock['lane_cores'][lane],
             'claimed_utc': utc(), 'environment_hash': lock['environment_sha256'],
             'implementation_lock_sha256': sha(IMPL), 'load_average_start': os.getloadavg()}
    write(run / 'claim.json', claim, exclusive=True)
    env = os.environ.copy()
    env.update(dict.fromkeys(THREADS, '1'))
    env.update(PYTHONPATH=str(HERE) + ':' + str(CLEAN / 'src'), PYTHONDONTWRITEBYTECODE='1',
               PYTHONHASHSEED='0', TMPDIR=str(RAW))
    logfile = RAW / f'{index:04d}.parent.log'
    with logfile.open('xb') as log:
        p = subprocess.Popen([str(PYTHON), '-B', str(HERE / 'stage2.py'), 'one', str(index)],
                             cwd=CLEAN, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write(run / 'parent-start.json', {'pid': p.pid, 'utc': utc()}, exclusive=True)
        try:
            rc = p.wait(timeout=195)
        except subprocess.TimeoutExpired:
            import psutil
            owned = psutil.Process(p.pid)
            children = owned.children(recursive=True)
            for child in reversed(children):
                try:
                    child.kill()
                except psutil.Error:
                    pass
            p.kill()
            p.wait(timeout=3)
            rc = p.returncode
            write(run / 'watchdog.json', {'utc': utc(), 'reason': '195s_command_watchdog'}, exclusive=True)
    record = read(run / 'record.json')
    if record is None:
        # This attempt remains failed forever. Never dispatch it again.
        write(run / 'launcher-failure.json', {'returncode': rc, 'utc': utc(),
                                             'no_retry': True, 'denominator_retained': True}, exclusive=True)
    return {'run_order': index, 'status': record['status'] if record else 'launcher_failure',
            'cpu_s': record['cpu_s'] if record else None,
            'wall_s': record['wall_s'] if record else None, 'returncode': rc}


def status():
    claims = sorted((OUT / 'runs').glob('*/claim.json'))
    records = [read(p) for p in sorted((OUT / 'runs').glob('*/record.json'))]
    from collections import Counter
    return {'claimed': len(claims), 'completed': len(records), 'planned': len(PLAN),
            'statuses': dict(Counter(r['status'] for r in records)),
            'missing_after_claim': len(claims) - len(records), 'load_average': os.getloadavg()}


def batch():
    import fcntl
    OUT.mkdir(exist_ok=True)
    with (OUT / 'batch.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock = locked_check()
        indices = []
        for lane in range(2):
            for i, row in enumerate(PLAN):
                if row['block'] % 2 == lane and not (OUT / 'runs' / f'{i:04d}' / 'claim.json').exists():
                    indices.append(i)
                    break
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            answers = list(pool.map(lambda i: launch(i, lock), indices))
        print(json.dumps({'trials': answers, 'progress': status()}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'batch', 'status', 'one'))
    parser.add_argument('index', nargs='?', type=int)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'batch':
        batch()
    elif args.command == 'status':
        print(json.dumps(status()))
    else:
        one(args.index)
