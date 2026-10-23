"""Q38 execution receipts; one immutable four-run batch per invocation.

Does not edit the prediction, inputs, schedule, solver, runner, or grading.
Run with the verified existing Python. Raw artifacts stay outside the checkout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import traceback

BASE = Path(__file__).resolve().parent
WORKSPACE = BASE.parents[2]
CLEAN = Path('/tmp/q38-58e3993-clean')
EXTERNAL = Path('/tmp/q38-58e3993-execution')
INPUT = CLEAN / 'jssa/difficulty/relabel-invariance'
PYTHON = Path('/home/kabatan/work/solver/.venv/bin/python')
COMMIT = '58e399315f259699e99cc1b190aa46c78d573e5a'
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value, *, new=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Only compact receipts are saved here. No small result-count assertion.
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with path.open('x' if new else 'w') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def git(*args, root=CLEAN):
    return subprocess.check_output(['git', *args], cwd=root, timeout=30).decode().strip()


def check_lock(base):
    lock = read(base / 'prediction.lock.json')
    errors = []
    for name, info in lock['files'].items():
        p = base / name
        if not p.is_file() or sha(p) != info['sha256'] or p.stat().st_size != info['bytes']:
            errors.append(name)
    for mapping, digest in [('files', 'file_manifest_sha256'),
                            ('all_transformed_dsl_sha256', 'all_transformed_dsl_manifest_sha256')]:
        raw = json.dumps(lock[mapping], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        if hashlib.sha256(raw).hexdigest() != lock[digest]:
            errors.append(digest)
    for mapping in ('transformation_rules_sha256', 'all_transformed_dsl_sha256'):
        for name, digest in lock[mapping].items():
            if sha(base / name) != digest:
                errors.append(name)
    if sha(base / 'prediction.md') != lock['prediction_sha256']:
        errors.append('prediction.md')
    if errors:
        raise RuntimeError('prediction lock mismatch: ' + repr(errors))
    return {'files': len(lock['files']), 'transformed_dsls': 200,
            'lock_sha256': sha(base / 'prediction.lock.json'), 'errors': errors}


def environment():
    plan = read(INPUT / 'execution-plan.json')
    return os.environ | plan['environment']


def preflight():
    os.chdir(CLEAN)
    sys.path[:0] = [str(CLEAN / 'src'), str(CLEAN)]
    from benchmarks import research_runner as runner
    from geosolver.runtime.integrity import verify_engine_lock
    checks = {str(p): check_lock(p) for p in (BASE, INPUT)}
    if git('rev-parse', 'HEAD') != COMMIT or git('status', '--porcelain'):
        raise RuntimeError('checkout is not clean at the authorized commit')
    protected = ['src', 'benchmarks/research_runner.py', 'benchmarks/cases.jsonl', 'pyproject.toml', 'uv.lock']
    if git('diff', FROZEN, '--', *protected):
        raise RuntimeError('frozen source mismatch')
    source = read(INPUT / 'source-manifest.json')
    for name, digest in source['files_sha256'].items():
        p = INPUT / source['snapshots'][name] if name in source['snapshots'] else CLEAN / name
        if sha(p) != digest:
            raise RuntimeError('source manifest mismatch: ' + name)
    fingerprint = runner.runtime_fingerprint()
    lock = verify_engine_lock()
    if fingerprint['issues'] or not lock[0]:
        raise RuntimeError('runtime/engine mismatch')
    cpus = runner._independent_cpus()[:4]
    if len(cpus) != 4 or None in cpus:
        raise RuntimeError('four independent CPUs are unavailable')
    topology = {str(c): {n: Path(f'/sys/devices/system/cpu/cpu{c}/topology/{n}').read_text().strip()
                         for n in ('physical_package_id', 'core_id', 'thread_siblings_list')} for c in cpus}
    versions = subprocess.check_output(['lscpu'], text=True)
    result = {'task': 'Q38', 'checked_at_utc': now(), 'solver_calls': 0,
              'authorization': 'Explicit user stage-2 authorization; commit and push confirmed by user.',
              'authorization_commit': COMMIT, 'commit_time_utc': git('show', '-s', '--format=%cI', COMMIT),
              'local_origin_tracking_ref': git('rev-parse', 'origin/claude/project-thread-9bdbbg', root=WORKSPACE),
              'push_evidence_limit': 'User confirmation plus local remote-tracking ref; no network access.',
              'checkout': str(CLEAN), 'sparse_checkout': True, 'git_dirty': False,
              'frozen_commit': FROZEN, 'frozen_src_tree': git('rev-parse', FROZEN + ':src'),
              'lock_checks': checks, 'source_manifest_files': len(source['files_sha256']),
              'runtime_fingerprint': fingerprint, 'engine_lock': lock,
              'python': sys.version, 'python_executable': str(PYTHON), 'machine': platform.uname()._asdict(),
              'lscpu': versions, 'cpus': cpus, 'topology': topology, 'loadavg': os.getloadavg(),
              'environment': read(INPUT / 'execution-plan.json')['environment'],
              'file_limit_bytes': 4900000, 'storage_note': 'Unmodified runner has no smaller result-size assertion; fixed prlimit applies. No compaction hook in solver.',
              'static_verify': {'documents': 240, 'batches': 210, 'solver_calls': 0, 'exit_code': 0},
              'implementation_sha256': sha(Path(__file__))}
    save(EXTERNAL / 'preflight.json', result, new=True)
    print(json.dumps({'preflight': 'passed', 'utc': result['checked_at_utc'], 'cpus': cpus}))


def paths(number):
    batch = read(INPUT / 'execution-plan.json')['batches'][number]
    dest = Path(batch['destination'].replace('<external-results-root>', str(EXTERNAL / 'campaigns')))
    receipt = EXTERNAL / 'receipts' / f'{number:03d}.json'
    return batch, dest, receipt


def start(number):
    pre = read(EXTERNAL / 'preflight.json')
    if pre['implementation_sha256'] != sha(Path(__file__)):
        raise RuntimeError('execution implementation changed after preflight')
    if number and read(paths(number - 1)[2]).get('state') != 'complete':
        raise RuntimeError('previous batch has not completed successfully; do not skip/retry')
    batch, dest, receipt = paths(number)
    if receipt.exists() or dest.exists():
        raise RuntimeError('batch already attempted; no reruns')
    if git('status', '--porcelain'):
        raise RuntimeError('execution checkout is dirty')
    check_lock(INPUT)
    if number == 0:
        save(EXTERNAL / 'execution-start.json', {
            'execution_started_at_utc': now(), 'authorization_commit': COMMIT,
            'prediction_lock_sha256': sha(INPUT / 'prediction.lock.json'),
            'source_hash': pre['runtime_fingerprint']['source_hash'],
            'cpus': pre['cpus'], 'loadavg': os.getloadavg(), 'planned_runs': 840}, new=True)
    save(receipt, {'batch': number, 'state': 'starting', 'start_requested_at_utc': now()}, new=True)
    log = EXTERNAL / 'receipts' / f'{number:03d}.launcher.log'
    with log.open('x') as output:
        process = subprocess.Popen([str(PYTHON), '-B', str(Path(__file__).resolve()), 'batch', str(number)],
                                   cwd=CLEAN, env=environment(), stdout=output, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    print(json.dumps({'batch': number, 'pid': process.pid, 'receipt': str(receipt), 'mode': batch['mode']}))


def batch_run(number):
    import psutil
    resource.setrlimit(resource.RLIMIT_FSIZE, (4900000, 4900000))
    batch, dest, receipt = paths(number)
    record = {'batch': number, 'block': batch['block'], 'mode': batch['mode'], 'seed': batch['seed'],
              'case_ids': batch['case_ids'], 'started_at_utc': now(), 'state': 'running',
              'controller_pid': os.getpid(), 'load_samples': [], 'commands': []}
    env = environment()
    argv = [x.replace('<verified-python3.12>', str(PYTHON)).replace('<external-results-root>', str(EXTERNAL / 'campaigns'))
            for x in batch['run_argv_after_separate_authorization']]
    prefix = ['prlimit', '--fsize=4900000:4900000', '--', str(PYTHON), '-B', '-m', 'benchmarks.research_runner']
    commands = [('run', argv), ('assess', prefix + ['assess', str(dest), '--cases', batch['cases']]),
                ('summarize', prefix + ['summarize', str(dest)])]
    try:
        for label, command in commands:
            log = EXTERNAL / 'receipts' / f'{number:03d}.{label}.log'
            with log.open('x') as stream:
                proc = subprocess.Popen(command, cwd=CLEAN, env=env, stdout=stream, stderr=subprocess.STDOUT)
                entry = {'label': label, 'argv': command, 'pid': proc.pid, 'started_at_utc': now()}
                record['commands'].append(entry)
                while True:
                    children = []
                    try:
                        for p in psutil.Process(proc.pid).children(recursive=True):
                            try:
                                children.append({'pid': p.pid, 'affinity': p.cpu_affinity(), 'threads': p.num_threads()})
                            except psutil.Error:
                                pass
                    except psutil.Error:
                        pass
                    record['load_samples'].append({'at_utc': now(), 'command': label,
                                                   'loadavg': os.getloadavg(), 'children': children})
                    save(receipt, record)
                    try:
                        code = proc.wait(timeout=10)
                        break
                    except subprocess.TimeoutExpired:
                        pass
                entry.update(returncode=code, finished_at_utc=now(), log_bytes=log.stat().st_size)
                if code:
                    raise RuntimeError(f'{label} returned {code}; stop without retry')
        record['summary'] = read(dest / 'summary.json')
        record['state'] = 'complete'
    except BaseException as error:
        record['state'] = 'stopped'
        record['error'] = repr(error)
        record['traceback'] = traceback.format_exc()
    record['finished_at_utc'] = now()
    record['final_loadavg'] = os.getloadavg()
    record['max_artifact_bytes'] = max((p.stat().st_size for p in dest.rglob('*') if p.is_file()), default=0)
    save(receipt, record)
    print(json.dumps({'batch': number, 'state': record['state'], 'error': record.get('error')}), flush=True)


def status():
    receipts = sorted((EXTERNAL / 'receipts').glob('*.json'))
    data = [read(p) for p in receipts]
    print(json.dumps({'batches_attempted': len(data), 'completed': sum(d.get('state') == 'complete' for d in data),
                      'last': {k: data[-1].get(k) for k in ('batch', 'state', 'mode', 'started_at_utc', 'finished_at_utc', 'error')} if data else None,
                      'loadavg': os.getloadavg()}, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['preflight', 'start', 'batch', 'status'])
    ap.add_argument('number', type=int, nargs='?')
    args = ap.parse_args()
    if args.action == 'preflight':
        preflight()
    elif args.action == 'start':
        start(args.number)
    elif args.action == 'batch':
        batch_run(args.number)
    else:
        status()
