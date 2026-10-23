"""Small archived-source replays. One solver job, one CPU, bounded output/time.

Run with the project's Python. prepare; run GROUP CASE --indices 0 1; then 2 3.
No frozen source is modified. Archives are read and copied only into /tmp.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tarfile
import tempfile
import time

OUT = Path(__file__).resolve().parent
ARCH = Path('/home/kabatan/work/solver-experiment/research-archives')
OLD = ARCH / '2026-09-08/local/benchmarks/local-evaluation/solver-improvement-20260907'
SPEED = ARCH / 'solver-evidence/optimization-speed-20261011'
LIMIT_BYTES = 4_900_000
ORDERS = {
    'norm': ['stage10-score-source', 'stage11-norm-source', 'stage11-norm-source', 'stage10-score-source'],
    'analytic': ['baseline-source', 'analytic-stable-v3-source', 'analytic-stable-v3-source', 'baseline-source'],
    'stability': ['stage8-scalar-budget-source', 'stage9-noadaptive-source', 'stage9-noadaptive-source', 'stage8-scalar-budget-source'],
}


def write_json(path, data):
    payload = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    assert len(payload.encode()) < LIMIT_BYTES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    scratch = Path(tempfile.mkdtemp(prefix='q33-replay-'))
    archive = SPEED / 'source-snapshots.tar.gz'
    index = json.loads((SPEED / 'source-snapshots.json').read_text())
    assert sha(archive) == index['sha256']
    hashes = {r['path']: r['sha256'] for r in index['files']}
    extracted = []
    with tarfile.open(archive) as tar:
        for member in tar:
            if member.name.split('/')[0] not in ORDERS['analytic'] or not member.isfile():
                continue
            path = scratch / member.name
            assert path.resolve().is_relative_to(scratch.resolve())
            assert member.size < LIMIT_BYTES
            data = tar.extractfile(member).read()
            assert hashlib.sha256(data).hexdigest() == hashes[member.name]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            extracted.append({'path': member.name, 'sha256': hashes[member.name], 'bytes': len(data)})
    sources = {v: str(OLD / v) for group in ('norm', 'stability') for v in ORDERS[group]}
    sources.update({v: str(scratch / v) for v in ORDERS['analytic']})
    differences = {}
    for group in ('norm', 'stability', 'analytic'):
        left, right = (Path(sources[v]) / 'src' for v in ORDERS[group][:2])
        assert {p.relative_to(left) for p in left.rglob('*.py')} == {
            p.relative_to(right) for p in right.rglob('*.py')}
        changes = []
        for p in sorted(left.rglob('*.py')):
            q = right / p.relative_to(left)
            if p.read_bytes() != q.read_bytes():
                changes.append({'path': str(p.relative_to(left)), 'before': sha(p), 'after': sha(q)})
        differences[group] = changes
        assert len(changes) == 1, changes
    inputs = {}
    case_files = [OLD / 'stage10-score-source/benchmarks/cases.jsonl',
                  ARCH / '2026-10-21/snapshot/benchmarks/cases.jsonl']
    wanted = {'HMMT-2011-FEB-ALGGEO-18', 'HMMT-2013-FEB-GEO-04',
              'HMMT-2023-FEB-GEO-04', 'HMMT-2024-FEB-GEO-10'}
    for file in case_files:
        for line in file.open():
            case = json.loads(line)
            if case['id'] not in wanted:
                continue
            dsl = case['dsl']
            p = OUT / 'inputs' / (case['id'] + '.json')
            if p.exists():
                assert json.loads(p.read_text()) == dsl
            else:
                write_json(p, dsl)
            inputs[case['id']] = dict(source=str(file), sha256=sha(p), reference=case['answer'])
    toy = {
        'id': 'zero-distance-precision', 'variables': ['x', 'y'],
        'constructions': [{'name': 'P', 'expression': 'Point(x,y)'},
                          {'name': 'Q', 'expression': 'Point(2,sqrt(2))'}],
        'conditions': [{'left': 'Distance(P,Q)', 'operator': '=', 'right': 0},
                       {'left': 'x', 'operator': '>', 'right': 0},
                       {'left': 'y', 'operator': '>', 'right': 0}],
        'target': 'x+y',
    }
    write_json(OUT / 'inputs/zero-distance-precision.json', toy)
    inputs[toy['id']] = dict(source=str(ARCH / '2026-10-21/snapshot/tests/test_solver_improvement_regressions.py') + ':19',
                            reference='2+sqrt(2)', sha256=sha(OUT / 'inputs/zero-distance-precision.json'))
    state = dict(scratch=str(scratch), sources=sources, differences=differences, inputs=inputs,
                 extracted_files=len(extracted), archive=str(archive), archive_sha256=sha(archive),
                 cpu=sorted(os.sched_getaffinity(0))[-1], python=sys.executable,
                 versions={p: importlib.metadata.version(p) for p in
                           ('numpy', 'scipy', 'sympy', 'mpmath', 'gmpy2', 'PyNomadBBO', 'pydantic')})
    write_json(OUT / 'replay-environment.json', state)
    print(json.dumps({k: state[k] for k in ('scratch', 'cpu', 'versions', 'differences')}), flush=True)


def run(group, case, indices, seed):
    state = json.loads((OUT / 'replay-environment.json').read_text())
    for index in indices:
        variant = ORDERS[group][index]
        source = Path(state['sources'][variant])
        stem = f'{group}--{case}--s{seed}--{index}'
        artifact = OUT / 'runs' / (stem + '.json')
        receipt = OUT / 'runs' / (stem + '.receipt.json')
        if receipt.exists():
            raise RuntimeError(f'Refusing to overwrite completed run: {receipt}')
        artifact.parent.mkdir(exist_ok=True)
        env = os.environ.copy()
        env.update(PYTHONPATH=str(source / 'src'), PYTHONDONTWRITEBYTECODE='1',
                   OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                   NUMEXPR_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1',
                   TMPDIR=state['scratch'], XDG_CACHE_HOME=state['scratch'])
        # September experiments explicitly used the Python mpmath backend.
        if group != 'analytic':
            env['MPMATH_NOGMPY'] = '1'
        else:
            env.pop('MPMATH_NOGMPY', None)
        budget = 180  # Archived public SolveOptions rejects budgets below 180 seconds.
        command = ['taskset', '-c', str(state['cpu']), sys.executable, '-m', 'geosolver.application.cli',
                   'solve', str(OUT / 'inputs' / (case + '.json')), '--time-limit-seconds', str(budget),
                   '--cores', '1', '--seed', str(seed), '--output', str(artifact)]

        def limit():
            resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT_BYTES, LIMIT_BYTES))

        started = time.monotonic()
        proc = subprocess.Popen(command, cwd=state['scratch'], env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, start_new_session=True, preexec_fn=limit)
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=75)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
        row = dict(group=group, case=case, seed=seed, index=index, variant=variant,
                   cpu=state['cpu'], process_wall_seconds=time.monotonic()-started,
                   solver_budget_seconds=budget, external_cap_seconds=75,
                   timed_out=timed_out, returncode=proc.returncode,
                   mpmath_backend='gmpy' if group == 'analytic' else 'python',
                   command=command, source=str(source), stdout_tail=stdout[-2000:], stderr_tail=stderr[-3000:])
        if artifact.exists():
            result = json.loads(artifact.read_text())
            diagnostics = result.get('diagnostics') or {}
            row.update(status=result['status'], answers=result.get('answers'),
                       engine=result.get('engine'), artifact_sha256=sha(artifact),
                       phase_timings=diagnostics.get('phase_timings'), counters=diagnostics.get('counters'))
        write_json(receipt, row)
        print(json.dumps({k: row.get(k) for k in ('group', 'case', 'index', 'variant', 'status',
                                                'process_wall_seconds', 'timed_out', 'answers', 'stderr_tail')}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('prepare')
    run_parser = sub.add_parser('run')
    run_parser.add_argument('group', choices=ORDERS)
    run_parser.add_argument('case')
    run_parser.add_argument('--indices', nargs='+', type=int, choices=range(4), default=[0, 1])
    run_parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    else:
        if len(args.indices) > 2:
            parser.error('At most two 75-second subprocesses per command')
        run(args.group, args.case, args.indices, args.seed)


if __name__ == '__main__':
    main()
