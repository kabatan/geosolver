"""Fixed development24, same-core ABBA, preserving all failures and exact sets."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import mean, median
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parent
PYTHON = Path('/home/kabatan/work/solver/.venv/bin/python')
DEST = ROOT / 'refinement-fallback-v4-abba'
VARIANTS = ('baseline-source', 'refinement-fallback-v4-source')
HASHES = {
    'baseline-source': 'sha256:f92ee9ba5bea9b124f19e79e95d89e47e66252fede326bb1a569eb1d318e969b',
    'refinement-fallback-v4-source': 'sha256:0d1a9570cc73cb3eee1196b839b7282f1c3de83f0a653713a940d2439124d954',
}
CASES = ROOT / 'screen-development/cases.jsonl'
records = [json.loads(line) for line in CASES.read_text().splitlines()]
identifiers = [row['id'] for row in records]
assert len(identifiers) == 24 and len(set(identifiers)) == 24
for row in records:
    for variant in VARIANTS:
        assert json.loads((ROOT / variant / 'benchmarks/dsl' / (row['id'] + '.json')).read_text()) == row['dsl']
previous = {}
for name in identifiers:
    raw = json.loads((ROOT / 'refinement-baseline-matched-screen/runs' / name / '0.json').read_text())
    previous[name] = raw['process']['elapsed_seconds']
identifiers.sort(key=lambda name: (-previous[name], name))
lanes, loads = {6: [], 7: []}, {6: 0., 7: 0.}
for name in identifiers:
    core = min(loads, key=loads.get)
    lanes[core].append(name)
    loads[core] += previous[name] * 4
DEST.mkdir(exist_ok=False)
(DEST / 'manifest.json').write_text(json.dumps({
    'protocol': 'same-core ABBA per case; original fixed development24 unchanged',
    'time_limit_seconds': 180, 'cores_per_solve': 1, 'seed': 0, 'jobs': 2,
    'source_hashes': HASHES, 'cases_sha256': sha256(CASES.read_bytes()).hexdigest(),
    'case_ids': identifiers, 'lanes': lanes, 'estimated_lane_seconds': loads,
    'include_failures': True, 'created_unix': time.time(),
}, indent=2) + '\n')
write_lock = threading.Lock()


def canonical_answers(answers):
    result = []
    for answer in answers:
        if answer['kind'] == 'algebraic':
            value = answer['value']
            result.append(('algebraic', tuple(value['minimal_polynomial']), value['real_root_index']))
        else:
            result.append((answer['kind'], json.dumps(answer['value'], sort_keys=True)))
    return sorted(result)


def lane(core, names):
    for name in names:
        order = (VARIANTS[0], VARIANTS[1], VARIANTS[1], VARIANTS[0])
        for position, variant in enumerate(order):
            repeat = 0 if position < 2 else 1
            env = os.environ.copy()
            env['PYTHONPATH'] = str(ROOT / variant / 'src')
            for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
                env[key] = '1'
            output = DEST / f'{name}--{position}--{variant}.json'
            start = time.monotonic()
            result = subprocess.run([
                'taskset', '-c', str(core), str(PYTHON), '-m', 'geosolver.application.cli', 'solve',
                str(ROOT / variant / 'benchmarks/dsl' / (name + '.json')),
                '--time-limit-seconds', '180', '--cores', '1', '--seed', '0', '--output', str(output),
            ], env=env, cwd=ROOT / variant, capture_output=True, text=True, timeout=190)
            elapsed = time.monotonic() - start
            if result.returncode:
                raise RuntimeError(f'{name}/{variant}: {result.returncode}: {result.stderr}')
            solver = json.loads(output.read_text())
            assert solver['engine']['source_hash'] == HASHES[variant]
            diagnostics = solver.get('diagnostics') or {}
            row = {
                'case': name, 'variant': variant, 'repeat': repeat, 'position': position, 'core': core,
                'process_wall_seconds': elapsed, 'solver_wall_seconds': solver['elapsed_seconds'],
                'source_hash': solver['engine']['source_hash'], 'answers': solver['answers'],
                'canonical_answers': canonical_answers(solver['answers']), 'status': solver['status'],
                'counters': diagnostics.get('counters', {}), 'phase_timings': diagnostics.get('phase_timings', {}),
                'raw_artifact': output.name,
            }
            with write_lock:
                with (DEST / 'records.jsonl').open('a') as stream:
                    stream.write(json.dumps(row) + '\n')
                print(json.dumps({'case': name, 'variant': variant, 'position': position, 'core': core,
                                  'wall': elapsed, 'status': solver['status']}), flush=True)


with ThreadPoolExecutor(max_workers=2) as pool:
    futures = [pool.submit(lane, core, names) for core, names in lanes.items()]
    for future in futures:
        future.result()
rows = [json.loads(line) for line in (DEST / 'records.jsonl').read_text().splitlines()]
assert len(rows) == 96
per_case = []
for name in identifiers:
    group = sorted((row for row in rows if row['case'] == name), key=lambda row: row['position'])
    per_case.append({
        'case': name, 'core': group[0]['core'],
        'canonical_equal_all_four': all(row['canonical_answers'] == group[0]['canonical_answers'] for row in group),
        'raw_descriptor_equal_all_four': all(row['answers'] == group[0]['answers'] for row in group),
        'status_equal_all_four': all(row['status'] == group[0]['status'] for row in group),
        **{variant: {'mean_process_seconds': mean(row['process_wall_seconds'] for row in group if row['variant'] == variant),
                     'mean_solver_seconds': mean(row['solver_wall_seconds'] for row in group if row['variant'] == variant),
                     'runs': [row['process_wall_seconds'] for row in group if row['variant'] == variant]}
           for variant in VARIANTS},
    })
summary = {
    'cases': 24, 'runs': 96, 'include_failures': True, 'same_core_per_case': True,
    'canonical_equal_cases': sum(row['canonical_equal_all_four'] for row in per_case),
    'raw_descriptor_equal_cases': sum(row['raw_descriptor_equal_all_four'] for row in per_case),
    'status_equal_cases': sum(row['status_equal_all_four'] for row in per_case),
}
for variant in VARIANTS:
    values = [row[variant]['mean_process_seconds'] for row in per_case]
    summary[variant] = {'sum_problem_means_seconds': sum(values), 'mean_problem_means_seconds': mean(values),
                        'median_problem_means_seconds': median(values),
                        'raw_run_sum_seconds': sum(row['process_wall_seconds'] for row in rows if row['variant'] == variant),
                        'status_counts': {status: sum(row['status'] == status for row in rows if row['variant'] == variant)
                                          for status in sorted({row['status'] for row in rows})}}
base = summary[VARIANTS[0]]['sum_problem_means_seconds']
new = summary[VARIANTS[1]]['sum_problem_means_seconds']
summary['process_sum_change_percent'] = 100 * (new / base - 1)
(DEST / 'summary.json').write_text(json.dumps({'summary': summary, 'cases': per_case}, indent=2) + '\n')
receipt_path = ROOT / 'refinement-receipt.json'
receipt = json.loads(receipt_path.read_text())
receipt['same_core_abba_v4'] = summary | {'path': str(DEST), 'manifest': 'manifest.json', 'raw': 'records.jsonl',
                                       'case_summary': 'summary.json',
                                       'limitation': 'Fixed24 development screen, seed0 only; full public323x3 and fresh holdout remain parent responsibility.'}
receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(summary), flush=True)
