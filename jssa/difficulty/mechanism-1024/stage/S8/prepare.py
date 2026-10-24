"""Preparation only: no solver execution, grading, commit or push."""
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
MECH = HERE.parents[1]
SOURCE = Path('/tmp/mechanism-7b-lkdjle5l/final')
EXPECTED = 'sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3'
BASE0 = '60db4b679b04167175c51c479c87c22fa663fda0'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(name, data):
    with (HERE / name).open('x') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def manifest(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}

def treehash(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob('*')):
        if (not p.is_file() or '__pycache__' in p.parts or 'frontend' in p.parts
                or p.name == 'engine-lock.json' or p.suffix not in {'.py', '.json', '.toml'}):
            continue
        h.update(p.relative_to(root).as_posix().encode() + b'\0'
                 + p.read_bytes().replace(b'\r\n', b'\n') + b'\0')
    return 'sha256:' + h.hexdigest()

def main():
    assert treehash(SOURCE / 'src/geosolver') == EXPECTED
    groups = {
        'G1': ['NO_NOMAD'], 'G2': ['NO_SECOND_ATTEMPT', 'NO_RESCUE'],
        'G3': ['NO_DIVERSE_SELECTION'], 'G4': ['NO_RESIDUAL_REWRITE', 'NO_SCALE_CHART'],
        'G5': ['NO_ALGEBRAIC'], 'G6': ['NO_ANALYTIC_JAC'],
    }
    cases = [('N', [])] + [('N+' + str(k), ['G' + str(k)]) for k in range(2, 7)]
    cases += [('C' + str(k), ['G' + str(j) for j in range(1, k + 1)]) for k in range(1, 6)]
    cases += [('BASE', list(groups))]
    threads = {k: '1' for k in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
               'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS', 'OMP_THREAD_LIMIT']}
    configs = []
    for name, enabled in cases:
        env = {'GEOSOLVER_ABLATE_' + switch: '0' if g in enabled else '1'
               for g, switches in groups.items() for switch in switches}
        configs.append(dict(name=name, enabled_groups=enabled, environment=env))
    save('configs.json', dict(source_hash=EXPECTED, configurations=configs, aliases={'N+1': 'C1'},
         environment_policy='Remove all inherited GEOSOLVER_* first, then set exactly environment plus thread_environment; SEARCH_MODE is unset.',
         thread_environment=threads, correctness_recorded_in_smoke=False))

    sources = [MECH / 'problem-set/problem-set.json',
               REPO / 'jssa/difficulty/capability-1024/preregistration-6.md']
    targets = []
    for group in ['a', 'b']:
        p = REPO / f'jssa/difficulty/unseen-2/{group}/cases.jsonl'
        sources.append(p)
        rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
        assert len(rows) == 17
        for row in rows:
            dsl = p.parent / row['dsl_path']
            targets.append(dict(case_id=row['id'], cohort='unseen34', subgroup=group,
                dsl_path=dsl.relative_to(REPO).as_posix(), input_sha256=sha(dsl)))
    old = json.loads((MECH / 'run-7b/pre-run-hashes.json').read_text())
    prior = {r['case_id']: r for r in old['inputs']}
    selected = json.loads(sources[0].read_text())
    dev = {r['id']: r for r in map(json.loads, (REPO / 'benchmarks/cases.jsonl').read_text().splitlines())}
    for group in ['hard', 'fast_algebraic', 'fast_search', 'multivalued']:
        for identifier in selected[group]:
            dsl = REPO / 'benchmarks' / dev[identifier]['dsl_path']
            assert sha(dsl) == prior[identifier]['sha256'], identifier
            targets.append(dict(case_id=identifier, cohort='mechanism72', subgroup=group,
                dsl_path=dsl.relative_to(REPO).as_posix(), input_sha256=sha(dsl)))
    assert len(targets) == len({r['case_id'] for r in targets}) == 106
    for row in targets:
        row['assignment_sha256'] = hashlib.sha256(row['case_id'].encode('utf-8')).hexdigest()
    targets.sort(key=lambda r: (r['assignment_sha256'], r['case_id']))
    for i, row in enumerate(targets):
        row.update(sha256_rank=i, machine='superPC' if i % 2 == 0 else 'WinPC')
    save('assignment.json', dict(rule='sha256(UTF-8 case_id), no prefix/newline, ascending hexadecimal; ties case_id; zero-based even rank superPC, odd WinPC; all seeds/configurations stay on assigned machine',
         counts={'total': 106, 'unseen34': 34, 'mechanism72': 72, 'superPC': 53, 'WinPC': 53},
         provenance_sha256={str(p.relative_to(REPO)): sha(p) for p in sources}, problems=targets))
    # Planned run order only. This script never launches these jobs.
    jobs = []
    for row in targets:
        for seed in [601, 602, 603]:
            offset = (row['sha256_rank'] + seed - 601) % 12
            order = configs[offset:] + configs[:offset]
            for config in order:
                jobs.append(dict(queue_index=len(jobs), case_id=row['case_id'], machine=row['machine'],
                    dsl_path=row['dsl_path'], input_sha256=row['input_sha256'], seed=seed,
                    configuration=config['name'], time_limit_seconds=180, cores=1))
    assert len(jobs) == 3816
    save('run-plan.json', dict(execution_authorized=False, jobs=jobs,
        order_rule='assignment sha256 rank outer, seed ascending, configurations rotated left by (rank + seed - 601) % 12'))
    patches = HERE / 'patches'
    patches.mkdir()
    paths = [MECH / 'run-7/jssa-ablation-67ad79a-vs-60db4b6.patch', MECH / 'switches/new-switches.patch']
    for p in paths:
        shutil.copyfile(p, patches / p.name)
    archive = subprocess.check_output(['git', '-C', str(REPO), 'archive', '--format=tar.gz', BASE0,
                                       'src', 'pyproject.toml', 'uv.lock'])
    (patches / 'base0-60db4b6.tar.gz').write_bytes(archive)
    receipts = []
    with tempfile.TemporaryDirectory(prefix='s8-reconstruct-') as tmp:
        root = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tf:
            tf.extractall(root, filter='data')
        baseline_hash = treehash(root / 'src/geosolver')
        for p in paths:
            result = subprocess.run(['git', 'apply', '--unsafe-paths', str(patches / p.name)],
                                    cwd=root, text=True, capture_output=True, check=True)
            receipts.append(dict(patch=p.name, original_path=p.relative_to(REPO).as_posix(),
                sha256=sha(p), resulting_source_hash=treehash(root / 'src/geosolver'),
                stdout=result.stdout, stderr=result.stderr))
        assert treehash(root / 'src/geosolver') == EXPECTED
        assert manifest(root / 'src') == manifest(SOURCE / 'src'), 'reconstruction differs'
    save('patches/reconstruction.json', dict(BASE0=BASE0, baseline_source_hash=baseline_hash,
        BASE1_source_hash=EXPECTED, steps=receipts, all_src_files_byte_identical=True,
        archive_sha256=sha(patches / 'base0-60db4b6.tar.gz')))
    save('source-hashes.json', dict(source=str(SOURCE), source_hash=EXPECTED,
         files_sha256=manifest(SOURCE), dependency_lock=json.loads((SOURCE / 'src/geosolver/dependency-lock.json').read_text())))
    smoke = ['AIME-2014-II-08', 'HMMT-2008-FEB-GEO-09']
    save('smoke-plan.json', dict(purpose='Switch wiring only; no correctness/answers recorded; no grading',
        source_hash=EXPECTED, seed=601, time_limit_seconds=20, outer_timeout_seconds=28,
        max_parallel=6, cores=1, retry=False,
        selection_reason='Fixed before smoke: two existing >=2-variable inputs, distance/radius constraints and IsTangent; no outcome-based selection.',
        jobs=[dict(index=i * 2 + j, configuration=c['name'], case_id=id,
            dsl_path='benchmarks/dsl/' + id + '.json', input_sha256=sha(REPO / 'benchmarks/dsl' / (id + '.json')))
            for i, c in enumerate(configs) for j, id in enumerate(smoke)]))
    print('Prepared 12 configurations, 106 problem assignments, 3816 UNEXECUTED planned jobs, 24 smoke jobs; patch reconstruction matches BASE1.')

if __name__ == '__main__':
    main()
