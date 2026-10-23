"""Resume only fixed batches 22..209, at most three solves per short command.

The frozen runner runs two immutable campaigns (three cases, then one). Their
unaltered runs and manifests are retained. A derived four-case manifest is used
solely for the registered amended assess_campaign/summarize_campaign path.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'amendment-null-diagnostics'))
import support as s

ROOT = Path('/tmp/q38-null-diagnostics-authorized-resume')
LOCAL = BASE / 'resume-records'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=s.CLEAN, text=True, timeout=15).strip()


def put(path, value, *, new=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if new:
        with path.open('x') as stream:
            stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
    else:
        temp = path.with_suffix('.tmp')
        s.save(temp, value)
        os.replace(temp, path)


def receipt_path(number, part):
    return ROOT / 'receipts' / f'{number:03d}.{part}.json'


def verify_inventory(root, expected):
    s.require(s.inventory(root) == expected, 'Artifact inventory changed: ' + str(root))


def common_checks():
    seal = s.read(ROOT / 'adapter-seal.json')
    s.require(seal['implementation_sha256'] == s.sha(Path(__file__)), 'Adapter changed after sealing')
    s.require(s.sha(ROOT / 'authorization.json') == seal['authorization_sha256'], 'Authorization changed')
    s.require(s.sha(ROOT / 'recovery-021.json') == seal['recovery_sha256'], 'Recovery receipt changed')
    recovery = s.read(ROOT / 'recovery-021.json')
    s.require(recovery['state'] == 'complete' and recovery['solver_calls'] == 0, 'Recovery not complete')
    verify_inventory(Path(recovery['recovered_campaign']), recovery['outputs'])
    s.require(s.sha(s.EXTERNAL / 'receipts/021.json') == recovery['original_stopped_receipt_sha256'],
              'Original stopped receipt changed')
    s.require(not (s.destination(s.plan()['batches'][21]) / 'assessment.jsonl').exists(),
              'Original stopped campaign was overwritten')
    s.check_supplement_lock()
    s.check_patch()
    s.check_original_lock(BASE)
    s.check_original_lock(s.CLEAN / 'jssa/difficulty/relabel-invariance')
    s.require(git('rev-parse', 'HEAD') == s.EXECUTION_COMMIT, 'Execution commit changed')
    s.require(not git('status', '--porcelain', '--untracked-files=all'), 'Dirty frozen checkout')
    s.require(not git('diff', s.FROZEN, '--', 'src', 'benchmarks/research_runner.py',
                      'benchmarks/cases.jsonl', 'pyproject.toml', 'uv.lock'), 'Frozen products changed')
    return seal


def seal():
    s.require(not (ROOT / 'adapter-seal.json').exists(), 'Adapter already sealed')
    recovery = s.read(ROOT / 'recovery-021.json')
    s.require(recovery['state'] == 'complete' and recovery['solver_calls'] == 0, 'Recovery incomplete')
    s.check_supplement_lock()
    s.check_patch()
    s.check_original_lock(BASE)
    s.require(not git('status', '--porcelain', '--untracked-files=all'), 'Dirty execution checkout')
    value = {'sealed_at_utc': s.now(), 'solver_calls': 0,
             'implementation_sha256': s.sha(Path(__file__)),
             'authorization_sha256': s.sha(ROOT / 'authorization.json'),
             'recovery_sha256': s.sha(ROOT / 'recovery-021.json'),
             'preflight_path': recovery['preflight_path'],
             'preflight_sha256': recovery['preflight_sha256'],
             'max_parallel_solves': 3, 'run_subprocess_timeout_seconds': 200,
             'outer_command_limit_seconds': 210,
             'batch_order': list(range(22, 210)), 'waves_in_plan_case_order': [3, 1],
             'no_solver_runner_or_grader_changes': True,
             'derived_manifest_note': 'Cases are joined in fixed batch order. Corpus hash is recomputed '
             'from those unchanged manifest case entries. Original wave manifests, layouts, UTCs and '
             'raw bytes remain available; no new trial or fabricated run is introduced.'}
    put(ROOT / 'adapter-seal.json', value, new=True)
    put(LOCAL / 'adapter-seal.json', value, new=True)
    shutil.copy2(recovery['preflight_path'], LOCAL / 'preflight.json')
    print({'state': 'sealed', 'solver_calls': 0, 'batches': [22, 209], 'max_parallel_solves': 3})


def validate_wave(destination, batch, identifiers):
    manifest = s.read(destination / 'campaign-manifest.json')
    s.require({r['id'] for r in manifest['cases']} == set(identifiers), 'Wave manifest cells mismatch')
    s.require(manifest['config']['seeds'] == [batch['seed']], 'Wrong seed')
    s.require(manifest['source_hash'] == s.SOURCE_HASH and not manifest['git_dirty']
              and not manifest['development_allow_dirty'], 'Noncanonical wave')
    s.require(manifest['execution_layout']['worker_count'] == len(identifiers), 'Wrong concurrency')
    paths = list((destination / 'runs').glob('*/*.json'))
    s.require(len(paths) == len(identifiers), 'Missing or extra outer run')
    for identifier in identifiers:
        raw = s.read(destination / 'runs' / identifier / f"{batch['seed']}.json")
        s.require(raw['case_id'] == identifier and raw['seed'] == batch['seed'], 'Wrong run key')
        s.require(not raw['execution_contract_issues'], 'Execution contract violation')
        s.require(raw['source_hash'] == s.SOURCE_HASH, 'Wrong run source hash')
        s.require(raw['config']['time_limit_seconds'] == 180 and raw['config']['cores'] == 1,
                  'Changed run budget')
        s.require(raw['process']['actual_affinity'] == [raw['process']['assigned_cpu']], 'Affinity mismatch')
        info = ((raw.get('solver_result') or {}).get('diagnostics') or {}).get('process_info')
        if info:
            s.require(info['import_root'] == str(s.CLEAN / 'src/geosolver'), 'Worker import mismatch')
            s.require(info['cpu_affinity'] == raw['process']['actual_affinity'], 'Worker affinity mismatch')
    for line in (destination / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        s.require(s.sha(destination / name) == digest, 'Wave checksum mismatch')


def wave(number, part):
    seal_record = common_checks()
    batch = s.plan()['batches'][number]
    path = receipt_path(number, part)
    destination = ROOT / 'waves' / f'{number:03d}-{part}'
    s.require(not path.exists() and not destination.exists(), 'Wave already attempted; no retries')
    s.require(not s.destination(batch).exists(), 'Final batch destination already exists')
    if part == 0 and number > 22:
        previous = s.read(receipt_path(number - 1, 'final'))
        s.require(previous['state'] == 'complete', 'Previous batch not complete')
        verify_inventory(Path(previous['destination']), previous['outputs'])
    if part == 1:
        previous = s.read(receipt_path(number, 0))
        s.require(previous['state'] == 'complete', 'First wave not complete')
        verify_inventory(Path(previous['destination']), previous['outputs'])
    identifiers = batch['case_ids'][:3] if part == 0 else batch['case_ids'][3:]
    argv = batch['run_argv_after_separate_authorization']
    argv = argv[:argv.index('--case-id')]
    argv = [x.replace('<verified-python3.12>', str(s.PYTHON)).replace(
        '<external-results-root>/' + s.destination(batch).name, str(destination)) for x in argv]
    argv[argv.index('--jobs') + 1] = str(len(identifiers))
    for identifier in identifiers:
        argv.extend(['--case-id', identifier])
    record = {'batch': number, 'wave': part, 'state': 'running', 'started_at_utc': s.now(),
              'mode': batch['mode'], 'seed': batch['seed'], 'case_ids': identifiers,
              'destination': str(destination), 'argv': argv, 'load_samples': [],
              'implementation_sha256': seal_record['implementation_sha256']}
    put(path, record, new=True)
    proc = None
    started = time.monotonic()
    try:
        import psutil
        log = path.with_suffix('.log')
        with log.open('x') as stream:
            proc = subprocess.Popen(argv, cwd=s.CLEAN, env=os.environ | s.plan()['environment'],
                                    stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            record['pid'] = proc.pid
            deadline = time.monotonic() + 200
            while True:
                children = []
                try:
                    for child in psutil.Process(proc.pid).children(recursive=True):
                        try:
                            children.append({'pid': child.pid, 'affinity': child.cpu_affinity(),
                                             'threads': child.num_threads()})
                        except psutil.Error:
                            pass
                except psutil.Error:
                    pass
                record['load_samples'].append({'at_utc': s.now(), 'loadavg': os.getloadavg(),
                                               'children': children})
                put(path, record)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Run command exceeded 200 seconds; stop without retry')
                try:
                    code = proc.wait(timeout=min(10, remaining))
                    break
                except subprocess.TimeoutExpired:
                    pass
        record['returncode'] = code
        s.require(code == 0, f'Frozen runner returned {code}; stop without retry')
        validate_wave(destination, batch, identifiers)
        record.update(state='complete', outputs=s.inventory(destination), raw_count=len(identifiers))
    except BaseException as error:
        if proc is not None and proc.poll() is None:
            try:
                import psutil
                children = psutil.Process(proc.pid).children(recursive=True)
                for child in reversed(children):
                    try:
                        child.kill()
                    except psutil.Error:
                        pass
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, psutil.Error):
                pass
            proc.wait(timeout=2)
        record.update(state='stopped', error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        record.update(finished_at_utc=s.now(), elapsed_seconds=time.monotonic()-started,
                      final_loadavg=os.getloadavg())
        put(path, record)
        put(LOCAL / path.name, record)
    print({'batch': number, 'wave': part, 'state': record['state'], 'raw_count': len(identifiers),
           'elapsed_seconds': record['elapsed_seconds']}, flush=True)


def finalize(number):
    common_checks()
    guard = s.install_no_solver_guard()
    batch = s.plan()['batches'][number]
    destination = s.destination(batch)
    path = receipt_path(number, 'final')
    s.require(not path.exists() and not destination.exists(), 'Finalization already attempted; do not retry')
    waves = [s.read(receipt_path(number, part)) for part in (0, 1)]
    s.require(all(r['state'] == 'complete' for r in waves), 'Wave incomplete')
    s.require(waves[0]['case_ids'] + waves[1]['case_ids'] == batch['case_ids'], 'Case order changed')
    s.require(waves[0]['finished_at_utc'] <= waves[1]['started_at_utc'], 'Waves overlapped')
    for wave_record in waves:
        verify_inventory(Path(wave_record['destination']), wave_record['outputs'])
    record = {'batch': number, 'state': 'running', 'started_at_utc': s.now(),
              'mode': batch['mode'], 'seed': batch['seed'], 'case_ids': batch['case_ids'],
              'destination': str(destination), 'solver_calls': 0,
              'wave_receipt_sha256': [s.sha(receipt_path(number, part)) for part in (0, 1)]}
    put(path, record, new=True)
    try:
        manifests = [s.read(Path(w['destination']) / 'campaign-manifest.json') for w in waves]
        differing = {'created_at_unix', 'corpus_hash', 'cases', 'execution_layout'}
        s.require({k:v for k,v in manifests[0].items() if k not in differing}
                  == {k:v for k,v in manifests[1].items() if k not in differing}, 'Wave manifest mismatch')
        manifest = copy.deepcopy(manifests[0])
        selected = {c['id']: c for m in manifests for c in m['cases']}
        s.require(len(selected) == 4, 'Duplicate manifest case')
        manifest['cases'] = [selected[i] for i in batch['case_ids']]
        manifest['corpus_hash'] = hashlib.sha256(s.canonical(manifest['cases'])).hexdigest()
        manifest['resume_wave_provenance'] = [
            {'path': str(Path(w['destination']) / 'campaign-manifest.json'),
             'sha256': s.sha(Path(w['destination']) / 'campaign-manifest.json'),
             'execution_layout': m['execution_layout'], 'created_at_unix': m['created_at_unix']}
            for w, m in zip(waves, manifests)]
        manifest['execution_layout']['sequential_wave_sizes'] = [3, 1]
        destination.mkdir(parents=True)
        s.save(destination / 'campaign-manifest.json', manifest)
        for w in waves:
            source = Path(w['destination'])
            for identifier in w['case_ids']:
                original = source / 'runs' / identifier / f"{batch['seed']}.json"
                target = destination / 'runs' / identifier / original.name
                target.parent.mkdir(parents=True)
                shutil.copy2(original, target)
                s.require(s.sha(original) == s.sha(target), 'Copied raw hash mismatch')
        inputs = s.inventory(destination)
        grader = s.load_grader()
        from geosolver.runtime.integrity import source_tree_hash
        s.require(source_tree_hash() == s.SOURCE_HASH, 'Wrong grading source')
        record['grader_patch'] = s.check_patch()
        record['inputs'] = inputs
        grader.assess_campaign(destination, cases_path=s.CLEAN / batch['cases'])
        record['assess_completed_at_utc'] = s.now()
        grader.summarize_campaign(destination)
        record['summarize_completed_at_utc'] = s.now()
        rows = [json.loads(line) for line in (destination / 'assessment.jsonl').read_text().splitlines()]
        s.require(len(rows) == 4 and {(r['case_id'], r['seed']) for r in rows}
                  == {(i, batch['seed']) for i in batch['case_ids']}, 'Assessment cells mismatch')
        missing = 0
        for row in rows:
            raw = s.read(destination / 'runs' / row['case_id'] / f"{row['seed']}.json")
            if ((raw.get('solver_result') or {}).get('error') or {}).get('code') == 'artifact_missing':
                missing += 1
                s.require(row['matched'] is False and row['normal_completion'] is False
                          and row['failure_stage'] == 'runtime', 'Incorrect missing-artifact handling')
        for name, entry in inputs.items():
            s.require(s.sha(destination / name) == entry['sha256'], 'Grading changed an input')
        s.check_guard(guard)
        record.update(state='complete', guard=guard, outputs=s.inventory(destination),
                      summary=s.read(destination / 'summary.json'), worker_artifact_missing=missing)
    except BaseException as error:
        record.update(state='stopped', error=repr(error), traceback=traceback.format_exc(), guard=guard)
        raise
    finally:
        record['finished_at_utc'] = s.now()
        put(path, record)
        put(LOCAL / path.name, record)
    print({'batch': number, 'state': record['state'], 'solver_calls_in_grading': 0,
           'matched': record['summary']['matched_count'], 'worker_artifact_missing': missing}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['seal', 'wave', 'finalize'])
    parser.add_argument('batch', type=int, nargs='?')
    parser.add_argument('part', type=int, nargs='?', choices=[0, 1])
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_FSIZE, (4900000, 4900000))
    if args.action == 'seal':
        seal()
        return
    s.require(args.batch is not None and 22 <= args.batch <= 209, 'Only batches 22..209 authorized')
    if args.action == 'wave':
        s.require(args.part in (0, 1), 'Specify wave 0 or 1')
        wave(args.batch, args.part)
    else:
        finalize(args.batch)


if __name__ == '__main__':
    main()
