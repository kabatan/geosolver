"""Verify frozen parent/temporary-cwd child imports; never launch a campaign.

Default: verify the supplement lock, too. --before-seal is stage-1 evidence only
and must never be accepted as the immediately-before-resumption check.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from support import (BASE, CLEAN, EXECUTION_COMMIT, EXTERNAL, FROZEN, HERE, PYTHON,
                     SOURCE_HASH, check_guard, check_original_lock, check_patch,
                     check_supplement_lock, destination, install_no_solver_guard,
                     now, plan, read, require, save, sha)


def probe():
    guard = install_no_solver_guard()
    # Deliberately do not repair sys.path: test the actual planned environment.
    import geosolver
    from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock
    spec = importlib.util.spec_from_file_location('q38_frozen_probe_runner',
                                                 CLEAN / 'benchmarks/research_runner.py')
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    fingerprint = runner.runtime_fingerprint()
    engine_lock = verify_engine_lock()
    files = {name: str(Path(module.__file__).resolve())
             for name, module in list(sys.modules.items())
             if name.startswith('geosolver') and getattr(module, '__file__', None)}
    require(Path(geosolver.__file__).resolve().parent == CLEAN / 'src/geosolver', 'Wrong import root')
    require(all(Path(path).is_relative_to(CLEAN / 'src') for path in files.values()),
            'Mixed geosolver import roots')
    require(source_tree_hash() == SOURCE_HASH, 'Wrong source hash')
    require(engine_lock[0] and not fingerprint['issues'], 'Engine/dependency mismatch')
    require(Path(sys.prefix) == PYTHON.parent.parent, 'Wrong dedicated environment')
    require('/home/kabatan/work/solver/src' not in sys.path, 'Old editable source on sys.path')
    check_guard(guard)
    print(json.dumps({'cwd': os.getcwd(), 'executable': sys.executable, 'prefix': sys.prefix,
                      'sys_path': sys.path, 'import_file': geosolver.__file__,
                      'source_hash': source_tree_hash(), 'runtime_fingerprint': fingerprint,
                      'engine_lock': engine_lock, 'imported_product_files': files,
                      'solver_calls': 0, 'guard': guard}))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=CLEAN, text=True, timeout=30).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--before-seal', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.probe:
        probe()
        return
    require(args.output is not None and not args.output.exists(), 'Supply a new --output path')
    guard = install_no_solver_guard(allow_processes=True)
    patch = check_patch()
    supplement = None if args.before_seal else check_supplement_lock()
    original = {str(base): check_original_lock(base)
                for base in (BASE, CLEAN / 'jssa/difficulty/relabel-invariance')}
    require(git('rev-parse', 'HEAD') == EXECUTION_COMMIT, 'Wrong execution checkout commit')
    require(not git('status', '--porcelain', '--untracked-files=all'), 'Execution checkout is dirty')
    protected = ['src', 'benchmarks/research_runner.py', 'benchmarks/cases.jsonl',
                 'pyproject.toml', 'uv.lock']
    require(not git('diff', FROZEN, '--', *protected), 'Frozen execution files changed')
    source = read(BASE / 'source-manifest.json')
    for name, digest in source['files_sha256'].items():
        path = BASE / source['snapshots'][name] if name in source['snapshots'] else CLEAN / name
        require(sha(path) == digest, f'Frozen manifest changed: {name}')
    # Verify the immutable files used for the 84-way regression, including batch 21.
    preserved = read(HERE / 'rescore-84/preserved-inputs.json')
    for name, entry in preserved['files'].items():
        path = EXTERNAL / name
        require(sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes'],
                f'Preserved execution file changed: {name}')
    pending = destination(plan()['batches'][21])
    require(not (pending / 'assessment.jsonl').exists(), 'Batch 21 must await separately authorized recovery')
    require(len(list((EXTERNAL / 'campaigns').glob('*/runs/*/*.json'))) == 88,
            'This resumption gate expects exactly the original 88 raw runs')
    env = os.environ | plan()['environment']
    argv = [str(PYTHON), '-B', str(Path(__file__).resolve()), '--probe']
    parent = json.loads(subprocess.check_output(argv, cwd=CLEAN, env=env, text=True, timeout=60))
    with tempfile.TemporaryDirectory(prefix='q38-null-diagnostics-import-probe-') as temporary:
        child = json.loads(subprocess.check_output(argv, cwd=temporary, env=env, text=True, timeout=60))
    require(parent['runtime_fingerprint'] == child['runtime_fingerprint'], 'Parent/child differ')
    expected_deps = read(BASE / 'execution-records/environment-repair.json')['child_probe']['dependencies']
    for name, version in parent['runtime_fingerprint']['runtime_dependencies'].items():
        require(expected_deps.get(name) == version, f'Dependency changed since repaired run: {name}')
    require(not git('status', '--porcelain', '--untracked-files=all'), 'Probe dirtied execution checkout')
    check_guard(guard)
    record = {'checked_at_utc': now(), 'status': 'passed', 'solver_calls': 0,
              'purpose': 'stage1_before_seal' if args.before_seal else 'immediately_before_authorized_resume',
              'execution_authorized_by_this_check': False,
              'clean_checkout': str(CLEAN), 'clean_commit': EXECUTION_COMMIT, 'frozen_commit': FROZEN,
              'git_dirty_before_and_after': False, 'source_manifest_files_checked': len(source['files_sha256']),
              'original_locks': original, 'supplement_lock': supplement, 'grader_patch': patch,
              'environment': plan()['environment'], 'argv': argv,
              'parent_probe': parent, 'temporary_cwd_child_probe': child, 'controller_guard': guard,
              'raw_count': 88, 'completed_assessments': 84, 'pending_batch_21': 4,
              'batch_21_assessed': False, 'remaining_solver_calls_not_started': 752,
              'limitations': 'Import probes model both working directories; they do not execute a worker. '
                            'The failed historical worker has no observable import trace.'}
    save(args.output, record)
    print({'status': 'passed', 'solver_calls': 0, 'parent_import': parent['import_file'],
           'child_import': child['import_file'], 'source_hash': parent['source_hash']})


if __name__ == '__main__':
    main()
