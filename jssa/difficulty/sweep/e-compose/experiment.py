"""Q43e: deterministic input selection and unmodified public solver execution.

Commands: prepare, run, one VARIANT SEED CPU. Raw results live outside the repo.
No reference answer is passed to solve(), and no solver function is patched.
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import copy
import csv
import datetime as dt
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RAW = Path('/tmp/q43e-compose-20261024')
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'
SOURCE = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
SELECT_SEED = 431024
SEEDS = [431, 947]
LIMIT = 180
JOBS = 3
THREAD_ENV = {k: '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                              'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}
os.environ.update(THREAD_ENV)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'src'), str(ROOT)))
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value, *, new=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if new:
        with path.open('x') as stream:
            stream.write(text)
    else:
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(text)
        temp.replace(path)


def rank(*values):
    return hashlib.sha256('|'.join(map(str, (SELECT_SEED, *values))).encode()).hexdigest()


def rename_expr(source, mapping):
    """Replace AST Name spans only; preserve decimal spelling and attributes."""
    if not isinstance(source, str):
        return source
    tree = ast.parse(source, mode='eval')
    starts = [0]
    for line in source.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    edits = [(starts[n.lineno-1] + n.col_offset,
              starts[n.end_lineno-1] + n.end_col_offset, mapping[n.id])
             for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in mapping]
    for lo, hi, replacement in sorted(edits, reverse=True):
        source = source[:lo] + replacement + source[hi:]
    return source


def rename(doc, mapping):
    out = copy.deepcopy(doc)
    out['variables'] = [mapping.get(v, v) for v in doc['variables']]
    for c in out['constructions']:
        c['name'] = mapping.get(c['name'], c['name'])
        c['expression'] = rename_expr(c['expression'], mapping)
    for c in out['conditions']:
        for key in ('left', 'right', 'predicate'):
            if key in c:
                c[key] = rename_expr(c[key], mapping)
    out['target'] = rename_expr(out['target'], mapping)
    return out


def verify_source():
    import geosolver
    from benchmarks.research_runner import runtime_fingerprint
    from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock
    subprocess.run(['git', 'diff', '--exit-code', FROZEN, '--', 'src'], cwd=ROOT,
                   check=True, capture_output=True)
    assert Path(geosolver.__file__).resolve().parent == ROOT / 'src/geosolver'
    assert source_tree_hash() == SOURCE
    assert verify_engine_lock()[0]
    fingerprint = runtime_fingerprint()
    assert not fingerprint['issues'], fingerprint
    return {'utc': now(), 'frozen_commit': FROZEN, 'fingerprint': fingerprint,
            'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'source_diff_empty': True, 'python': sys.executable, 'loadavg': os.getloadavg(),
            'script_sha256': digest(Path(__file__).read_bytes())}


def prepare():
    from geosolver.problem.adapter import _target_to_engine
    from geosolver.problem.models import GeometryProblem
    from geosolver.problem.validation import validate
    from benchmarks.research_runner import reference_expressions

    preflight = verify_source()
    assert not (HERE / 'manifest.json').exists(), 'Do not replace an existing selection'
    sources = [('development', 'benchmarks/cases.jsonl', 10),
               ('unused_aime', 'jssa/difficulty/unseen-2/a/cases.jsonl', 5),
               ('unused_hmmt', 'jssa/difficulty/unseen-2/b/cases.jsonl', 5)]
    selected, universe, source_hashes = [], [], {}
    for pool, path, n in sources:
        data = (ROOT / path).read_bytes()
        source_hashes[path] = digest(data)
        rows = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
        rows.sort(key=lambda row: (rank('select', pool, row['id']), row['id']))
        # Eligibility is only the presence of a runnable DSL, never solver success/difficulty.
        eligible = [r for r in rows if isinstance(r.get('dsl'), dict)
                    and r.get('authoring_status', 'runnable') == 'runnable']
        chosen = {r['id'] for r in eligible[:n]}
        for row in rows:
            universe.append({'pool': pool, 'id': row['id'], 'rank_hash': rank('select', pool, row['id']),
                             'selected': row['id'] in chosen,
                             'eligible': row in eligible})
        for row in eligible[:n]:
            selected.append({'pool': pool, 'source_path': path, 'id': row['id'],
                             'dsl': row['dsl'], 'answer': row['answer'],
                             'rank_hash': rank('select', pool, row['id'])})
    assert len(selected) == 20 and len({r['id'] for r in selected}) == 20
    bases, base_meta, variants = [], [], []

    def add(doc, kind, components, **extra):
        report = validate(GeometryProblem.model_validate(doc))
        # Invalid transformations remain scheduled and count in the denominator.
        item = {'id': doc['id'], 'kind': kind, 'components': components,
                'n_vars': len(doc['variables']), 'n_conditions': len(doc['conditions']),
                'input_sha256': digest(doc), 'valid': report.valid,
                'validation_issues': [v.model_dump() for v in report.issues], **extra}
        save(HERE / 'inputs' / (doc['id'] + '.json'), doc, new=True)
        variants.append(item)

    for i, row in enumerate(selected):
        original = row['dsl']
        names = original['variables'] + [c['name'] for c in original['constructions']]
        mapping = {name: f'q{i:02d}_{name}' for name in names}
        doc = rename(original, mapping)
        assert rename(doc, {v: k for k, v in mapping.items()}) == original
        # Public adapter special-cases a top-level Degrees target. Apply identically to all variants.
        doc['target'] = _target_to_engine(doc['target'])
        doc['id'] = f'single-{i:02d}'
        bases.append(doc)
        ans = row['answer'] if isinstance(row['answer'], list) else [row['answer']]
        refs = [expr for a in ans for expr in reference_expressions(str(a))]
        base_meta.append({k: v for k, v in row.items() if k != 'dsl'} | {
            'index': i, 'n_vars': len(doc['variables']), 'references': refs,
            'source_dsl_sha256': digest(original), 'namespace': mapping,
            'target_normalized': doc['target']})
        add(doc, 'single', [i], references=refs)
        eq = [j for j, c in enumerate(doc['conditions']) if c.get('operator') == '=']
        eq.sort(key=lambda j: (rank('split', row['id'], j), j))
        halves = [set(eq[::2]), set(eq[1::2])]
        for h in (0, 1):
            part = copy.deepcopy(doc)
            part['id'] = f'half{h}-{i:02d}'
            retained = [j for j, c in enumerate(doc['conditions'])
                        if c.get('operator') != '=' or j in halves[h]]
            part['conditions'] = [doc['conditions'][j] for j in retained]
            add(part, 'half' + str(h), [i], retained_conditions=retained,
                split_equalities=len(eq), references=refs,
                grading_note='Relaxation; reference equality is descriptive, not correctness.')
        assert halves[0].isdisjoint(halves[1]) and halves[0] | halves[1] == set(eq)

    pairs = [[i, i+10] for i in range(10)]
    quads = [pairs[i] + pairs[i+1] for i in range(0, 10, 2)]
    for kind, groups in [('pair', pairs), ('quad', quads)]:
        for g, components in enumerate(groups):
            combined = {key: list(itertools.chain.from_iterable(bases[i][key] for i in components))
                        for key in ('variables', 'constructions', 'conditions')}
            assert len(combined['variables']) == len(set(combined['variables']))
            modes = ('sum', 'left', 'right') if kind == 'pair' else ('sum',)
            for mode in modes:
                doc = copy.deepcopy(combined)
                doc['id'] = f'{kind}-{mode}-{g:02d}'
                targets = components if mode == 'sum' else [components[0 if mode == 'left' else 1]]
                doc['target'] = ' + '.join(f'({bases[i]["target"]})' for i in targets)
                refs = [' + '.join(f'({r})' for r in rs) for rs in itertools.product(
                    *(base_meta[i]['references'] for i in targets))]
                add(doc, kind + '_' + mode, components, references=refs, group=g,
                    target_components=targets)

    jobs = [{'variant': v['id'], 'seed': seed} for v in variants for seed in SEEDS]
    jobs.sort(key=lambda j: rank('schedule', j['variant'], j['seed']))
    manifest = {'created_utc': now(), 'selection_seed': SELECT_SEED, 'solver_seeds': SEEDS,
                'time_limit_seconds': LIMIT, 'jobs_max': JOBS, 'raw_directory': str(RAW),
                'source_hash': SOURCE, 'source_files_sha256': source_hashes,
                'selected': base_meta, 'pairs': pairs, 'quads': quads,
                'variants': variants, 'schedule': jobs,
                'hypotheses': None, 'selection_rule': 'SHA256(seed|select|pool|id), then id; 10/5/5',
                'split_rule': 'Retain every non-equality in both; alternate hash-sorted equality indices',
                'baseline_note': 'Global namespace also applied to single baselines; no rename confound within sweep.',
                'unused_note': 'Named unused pools; existing results not consulted. Not a claim of virgin global holdout.'}
    save(HERE / 'preflight.json', preflight, new=True)
    save(HERE / 'manifest.json', manifest, new=True)
    with (HERE / 'selection-universe.csv').open('x') as f:
        writer = csv.DictWriter(f, fieldnames=list(universe[0]))
        writer.writeheader()
        writer.writerows(universe)
    print(json.dumps({'selected': len(selected), 'variants': len(variants), 'runs': len(jobs),
                      'invalid_inputs': [v['id'] for v in variants if not v['valid']],
                      'cases': [{k: r[k] for k in ('id', 'pool', 'n_vars')} for r in base_meta]}))


def one(variant, seed, cpu):
    os.sched_setaffinity(0, {cpu})
    from geosolver.application.service import solve
    from geosolver.engine.runner import EngineRunner
    import geosolver
    from geosolver.runtime.integrity import source_tree_hash
    assert source_tree_hash() == SOURCE
    path = RAW / 'runs' / f'{variant}__s{seed}.json'
    doc = read(HERE / 'inputs' / f'{variant}.json')
    started = time.monotonic()
    record = {'variant': variant, 'seed': seed, 'cpu': cpu, 'started_utc': now(),
              'load_start': os.getloadavg(), 'input_sha256': digest(doc),
              'parent_import_root': str(Path(geosolver.__file__).resolve().parent),
              'source_hash': SOURCE}
    try:
        result = solve(doc, {'time_limit_seconds': LIMIT, 'cores': 1, 'seed': seed},
                       runner=EngineRunner(memory_limit_bytes=2 * 1024**3))
        record['solver_result'] = result.model_dump(mode='json')
        info = (record['solver_result'].get('diagnostics') or {}).get('process_info', {})
        issues = []
        if info and info.get('import_root') != str(ROOT / 'src/geosolver'):
            issues.append('worker_import_root_mismatch')
        if info and info.get('cpu_affinity') != [cpu]:
            issues.append('worker_affinity_mismatch')
        if result.engine.source_hash != SOURCE:
            issues.append('source_hash_mismatch')
        record['execution_contract_issues'] = issues
    except BaseException:
        record['error'] = traceback.format_exc()
    record.update(finished_utc=now(), elapsed_seconds=time.monotonic()-started,
                  load_end=os.getloadavg())
    save(path, record, new=True)


def run():
    import psutil
    verify_source()
    manifest = read(HERE / 'manifest.json')
    assert manifest['source_hash'] == SOURCE
    RAW.mkdir(parents=True, exist_ok=True)
    assert not (RAW / 'execution-start.json').exists(), 'Use a new explicit campaign for any rerun'
    available = sorted(os.sched_getaffinity(0))
    # Deterministic representatives; avoid the first CPU where default workers often land.
    cpus = [available[i] for i in (11, 21, 29)] if len(available) >= 30 else available[-3:]
    assert len(cpus) == JOBS
    save(RAW / 'execution-start.json', {'utc': now(), 'manifest_sha256': digest(manifest),
                                      'cpus': cpus, 'planned_runs': len(manifest['schedule']),
                                      'loadavg': os.getloadavg()}, new=True)
    from queue import Queue
    slots = Queue()
    for cpu in cpus:
        slots.put(cpu)
    for folder in ('runs', 'logs', 'receipts'):
        (RAW / folder).mkdir(exist_ok=True)

    def launch(job):
        cpu = slots.get()
        key = f'{job["variant"]}__s{job["seed"]}'
        start = time.monotonic()
        receipt = {**job, 'cpu': cpu, 'started_utc': now()}
        try:
            with (RAW / 'logs' / (key + '.log')).open('x') as log:
                process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                    'one', job['variant'], str(job['seed']), str(cpu)], cwd=ROOT,
                    env=os.environ.copy(), stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True)
                try:
                    code = process.wait(timeout=LIMIT+45)
                    receipt['returncode'] = code
                except subprocess.TimeoutExpired:
                    receipt['external_timeout'] = True
                    root = psutil.Process(process.pid)
                    children = root.children(recursive=True)
                    for child in reversed(children):
                        try:
                            child.kill()
                        except psutil.Error:
                            pass
                    process.kill()
                    process.wait(timeout=10)
                receipt['raw_exists'] = (RAW / 'runs' / (key + '.json')).exists()
        except BaseException:
            receipt['error'] = traceback.format_exc()
        finally:
            receipt.update(finished_utc=now(), elapsed_seconds=time.monotonic()-start)
            save(RAW / 'receipts' / (key + '.json'), receipt, new=True)
            slots.put(cpu)
        return receipt

    with concurrent.futures.ThreadPoolExecutor(max_workers=JOBS) as pool:
        futures = [pool.submit(launch, job) for job in manifest['schedule']]
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            receipt = future.result()
            completed += 1
            save(RAW / 'progress.json', {'completed': completed, 'total': len(futures),
                 'updated_utc': now(), 'last': receipt, 'loadavg': os.getloadavg()})
            print(json.dumps({'completed': completed, 'total': len(futures),
                              'variant': receipt['variant'], 'seed': receipt['seed'],
                              'seconds': round(receipt['elapsed_seconds'], 2)}), flush=True)
    save(RAW / 'execution-end.json', verify_source(), new=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'run', 'one'])
    parser.add_argument('args', nargs='*')
    args = parser.parse_args()
    if args.command == 'one':
        one(args.args[0], int(args.args[1]), int(args.args[2]))
    else:
        globals()[args.command]()
