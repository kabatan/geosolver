"""Validate and hash preparation; emit a queue specification, never run jobs."""
import ast
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys

from prepare_common import IMPL, OUT, REPO, STAGE, identity, save, sha, source_manifest


def main():
    source = source_manifest()
    targets_doc = json.loads((OUT / 'targets.json').read_text())
    targets = targets_doc['targets']
    groups = json.loads((OUT / 'groups.json').read_text())
    assert len(targets) == len({t['identity'] for t in targets}) == 44
    original_contacts = json.loads((STAGE / 'S3/contacts.json').read_text())['cases']
    original_s5 = json.loads((STAGE / 'S5/targets.json').read_text())['targets']
    development = json.loads((OUT / 'selection-audit.json').read_text())['development_IsTangent']
    required = {identity(c['case_id']) for c in original_contacts + original_s5} | set(development)
    assert {t['identity'] for t in targets} == required
    assert targets_doc['selection_script_sha256'] == sha(OUT / 'select_targets.py')
    assert groups['script_sha256'] == sha(OUT / 'classify_groups.py')
    assert {c['identity'] for c in groups['cases']} == required
    assigned = [c for v in groups['groups'].values() for c in v]
    assert len(assigned) == len(set(assigned)) == 44
    assert groups['group_counts'] == {'接点効果群': 6, '同式群': 33, 'その他': 5}
    evidence = json.loads((OUT / 'grouping-evidence.json').read_text())
    assert len(evidence['syntax_formula_discrepancies']) == 15
    for r in groups['cases']:
        e = r['evidence']
        criterion = (e['residual_bytes_identical'] and e['formulas_identical']
                     if 'residual_bytes_identical' in e else e['no_T2_contact_expression'])
        assert r['same_formula_criterion'] == criterion
        expected = '接点効果群' if r['contact_effect_reason'] else '同式群' if criterion else 'その他'
        assert r['group'] == expected
    input_hashes = {}
    for t in targets:
        assert sha(REPO / t['dsl_path']) == t['sha256']
        input_hashes[t['dsl_path']] = t['sha256']
        for o in t['occurrences']:
            assert sha(REPO / o['path']) == o['sha256']
            input_hashes[o['path']] = o['sha256']
    for doc in [targets_doc, groups]:
        for relative, expected in doc['source_files_sha256'].items():
            assert sha(REPO / relative) == expected, relative
    saved_source = json.loads((OUT / 'source-hashes.json').read_text())
    assert saved_source == source
    scope = json.loads((OUT / 'switch-scope-evidence.json').read_text())
    assert scope['source_hash'] == source['source_hash']
    for rel, entry in scope['functions'].items():
        assert sha(IMPL / rel) == entry['sha256']
    # Read existing oracle metadata, never a solver/candidate result or pickle.
    s1_manifest = Path('/tmp/mechanism-S1-1m9aomj8/manifest.json')
    s1 = json.loads(s1_manifest.read_text())
    s1_inputs = {identity(c['case_id']): c for c in s1['inputs']}
    references, reference_hashes = [], {str(s1_manifest): sha(s1_manifest)}
    for t in targets:
        if t['identity'] in s1_inputs:
            old = s1_inputs[t['identity']]
            assert old['sha256'] == t['sha256']
            expressions = old['reference_expressions']
            origin = str(s1_manifest)
            initial = s1_manifest.parent / 'runs' / t['case_id'] / 'initial.pkl'
            saved = next(c for c in groups['cases'] if c['identity'] == t['identity'])['evidence']
            assert sha(initial) == saved['initial_pickle_sha256']
            reference_hashes[str(initial)] = sha(initial)  # bytes only; no unpickle
        else:
            p = STAGE / 'S5/inputs' / (t['case_id'] + '.json')
            old = json.loads(p.read_text())
            assert old['dsl'] == json.loads((REPO / t['dsl_path']).read_text())
            expressions = old['reference_expressions']
            origin = str(p.relative_to(REPO))
            reference_hashes[origin] = sha(p)
        references.append(dict(case_id=t['case_id'], origin=origin,
                               reference_expressions=expressions,
                               available=bool(expressions), independently_revalidated=False))
    missing = [r['case_id'] for r in references if not r['available']]
    assert set(missing) == {'HMMT-2013-FEB-TEAM-03', 'HMMT-2022-FEB-TEAM-03'}
    save('reference-sources.json', dict(status='existing reference expressions only; no evaluation or canonicalization performed',
        sources_sha256=reference_hashes, missing=missing, cases=references))
    jobs = []
    for i, t in enumerate(targets):
        for j, seed in enumerate([501, 502, 503]):
            modes = ['T2', 'T1'] if (i + j) % 2 == 0 else ['T1', 'T2']
            for mode in modes:
                jobs.append(dict(queue_index=len(jobs), case_id=t['case_id'], identity=t['identity'],
                    dsl_path=t['dsl_path'], input_sha256=t['sha256'], seed=seed, configuration=mode,
                    tangency_mode_environment=None if mode == 'T2' else 'T1',
                    time_limit_seconds=180, cores=1, internal_threads=1))
    assert len(jobs) == len({(j['identity'], j['seed'], j['configuration']) for j in jobs}) == 264
    first_counts = Counter(jobs[k]['configuration'] for k in range(0, len(jobs), 2))
    assert first_counts == {'T1': 66, 'T2': 66}
    save('run-plan.json', dict(status='DESIGN_ONLY_DO_NOT_EXECUTE', solver_executed=False,
        source_hash=source['source_hash'], seeds=[501,502,503], configurations=['T2','T1'],
        task_count=len(jobs), maximum_parallel=12, time_limit_seconds=180,
        order='FIFO: sorted identity, then seed ascending, then rotating configuration order (problem_index+seed_index)%2',
        first_configuration_counts=dict(first_counts),
        cpu_policy='one distinct eligible CPU per active slot; min(12, affinity CPU count); inherit to all descendants',
        thread_environment={k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS',
            'NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS','OMP_THREAD_LIMIT']},
        no_retries=True, skip_solved_problems=False, jobs=jobs))
    # Product code is parsed/read only. Preparation scripts import no product
    # modules and never call subprocess/process APIs.
    for p in OUT.glob('*.py'):
        tree = ast.parse(p.read_text())
        assert not any(isinstance(n, ast.Import) and any(a.name.split('.')[0] in
            {'subprocess','multiprocessing','geosolver'} for a in n.names) or
            isinstance(n, ast.ImportFrom) and (n.module or '').split('.')[0] in
            {'subprocess','multiprocessing','geosolver'} for n in ast.walk(tree)), p
    protected = [STAGE / 'S3/preregistration-13.md', STAGE / 'S3/preregistration-12.md',
        STAGE / 'S3/check_stage1.py', STAGE / 'S3/switch-check.json',
        STAGE / 'S3/contacts.json', STAGE / 'S5/targets.json', STAGE / 'S5/classification.csv']
    files = {str(p.relative_to(REPO)):sha(p) for p in sorted(OUT.iterdir())
             if p.is_file() and p.name != 'preparation-hashes.json'}
    for p in OUT.iterdir():
        if p.is_file():
            assert p.stat().st_size < 3_000_000
    intended_python = Path(s1['python'])
    save('preparation-hashes.json', dict(created_utc=datetime.now(timezone.utc).isoformat(),
        status='PREPARATION_COMPLETE_MEASUREMENT_NOT_RUN', source_hash=source['source_hash'],
        files_sha256=files, input_occurrences_sha256=input_hashes,
        protected_source_files_sha256={str(p.relative_to(REPO)):sha(p) for p in protected},
        reference_provenance_sha256=reference_hashes,
        preparation_python=dict(executable=sys.executable, resolved=str(Path(sys.executable).resolve()),
            sha256=sha(Path(sys.executable).resolve()), version=sys.version),
        planned_solver_python=dict(path=str(intended_python), resolved=str(intended_python.resolve()),
            sha256=sha(intended_python.resolve()), executed=False),
        dependency_lock_sha256=sha(IMPL / 'dependency-lock.json'),
        host=platform.node(), platform=platform.platform(), available_cpus=sorted(os.sched_getaffinity(0)),
        checks=dict(exact_union=True, unique_targets=44, disjoint_exhaustive_groups=True,
            group_counts=groups['group_counts'], syntax_formula_discrepancies=15,
            planned_jobs=264, configuration_first_counts=dict(first_counts),
            all_recorded_hashes_match=True, no_product_imports_in_preparation_scripts=True),
        limitations=dict(same_formula_label_does_not_prove_identity_for=15,
            missing_existing_reference_expressions=missing, references_not_revalidated=True),
        solver_executed=False, search_executed=False, refinement_executed=False,
        final_verification_executed=False, identification_executed=False,
        measurement_seeds_executed=[], implementation_modified=False,
        git_commit_executed=False, git_push_executed=False))
    print('S6 preparation checked: 44 targets, groups 6/33/5, 264 planned jobs; no solver execution')


if __name__ == '__main__':
    main()
