"""Read-only analysis of the fixed Q43c campaign; never launches solver jobs.

Run with the original venv and PYTHONDONTWRITEBYTECODE=1. --partial writes only
an explicitly incomplete preview outside the repository. Final analysis requires
all scheduled receipts. Original-answer scoring imports the byte-checked frozen
benchmark assessor. Swapped targets have no independent answer-set reference.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
import datetime as dt
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

from common import BASE, ROOT, RAW, FROZEN, SOURCE, KINDS, SEEDS, digest, read, save, sha, verify_source


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def finite_number(value):
    import math
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError, OverflowError):
        return None


def coordinate_distance(left, right):
    """Descriptive coordinate distance, not an acceptance/scoring threshold."""
    if not left or not right or len(left) != len(right):
        return None
    if any(x is None for x in [*left, *right]):
        return None
    return max(abs(a - b) / max(1.0, abs(a), abs(b)) for a, b in zip(left, right))


def verify_inputs():
    source = verify_source()
    manifest = read(BASE / 'resume-manifest.json')
    selection = read(BASE / 'selection.json')
    jobs = read(BASE / 'schedule.json')
    assert len(jobs) == 200 and len(selection['cases']) == 20
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == FROZEN
    clean_base = ROOT / 'jssa/difficulty/sweep/c-swap-target'
    for name in ['selection.json', 'schedule.json']:
        assert sha(BASE / name) == manifest[name.replace('.json', '_sha256')]
        assert (BASE / name).read_bytes() == (clean_base / name).read_bytes()
    for name, expected in manifest['code_sha256'].items():
        assert sha(BASE / name) == expected == sha(clean_base / name), name
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    target_only = []
    for case in selection['cases']:
        reference_path = BASE / 'references' / f'{case["id"]}.json'
        assert reference_path.read_bytes() == (clean_base / 'references' / reference_path.name).read_bytes()
        assert read(reference_path)['truth_status'] == 'verified'
        original = read(BASE / case['variants']['original']['path'])
        original_compiled = GeometryProblem.model_validate(original).engine_document()
        original_bundle = load_problem_bundle(original_compiled)
        def without_target(bundle):
            spec = asdict(bundle.spec)
            spec.pop('answer_expr')
            return spec
        for kind, variant in case['variants'].items():
            path = BASE / variant['path']
            value = read(path)
            assert digest(value) == variant['dsl_sha256']
            assert path.read_bytes() == (clean_base / variant['path']).read_bytes()
            assert {k: v for k, v in value.items() if k != 'target'} == {k: v for k, v in original.items() if k != 'target'}
            compiled = GeometryProblem.model_validate(value).engine_document()
            assert {k: v for k, v in compiled.items() if k != 'answer'} == {k: v for k, v in original_compiled.items() if k != 'answer'}
            bundle = load_problem_bundle(compiled)
            assert without_target(bundle) == without_target(original_bundle)
            assert bundle.var_names == original_bundle.var_names
            target_only.append({'id': case['id'], 'kind': kind, 'compiled_conditions_unchanged': True})
    scorer_path = ROOT / 'benchmarks/research_runner.py'
    import benchmarks.research_runner as scorer
    assert Path(scorer.__file__).resolve() == scorer_path
    frozen_bytes = subprocess.check_output(['git', 'show', FROZEN + ':benchmarks/research_runner.py'], cwd=ROOT)
    assert frozen_bytes == scorer_path.read_bytes()
    return selection, jobs, {'source': source, 'frozen_commit': FROZEN,
        'selection_sha256': sha(BASE / 'selection.json'), 'schedule_sha256': sha(BASE / 'schedule.json'),
        'harness_sha256': manifest['code_sha256'], 'scorer_sha256': sha(scorer_path),
        'compiled_target_only_variants': len(target_only), 'analysis_sha256': sha(Path(__file__))}


def summarize_run(job, cases, expected_keys, expected_dependencies):
    from benchmarks.research_runner import _answer_keys, read_run_outcome
    from geosolver.application.service import problem_hash
    from geosolver.problem.models import GeometryProblem
    folder = RAW / 'runs' / f'{job["index"]:03d}'
    receipt_path = folder / 'receipt.json'
    receipt = read(receipt_path)
    assert receipt['job'] == job
    result = receipt.get('result') or {}
    diag = result.get('diagnostics') or {}
    summary = diag.get('pipeline_summary') or {}
    process = diag.get('process_info') or {}
    artifact_path = folder / 'artifact.json'
    artifact = read(artifact_path) if artifact_path.exists() else {}
    if result:
        assert receipt['source']['source_hash'] == SOURCE
        assert receipt['source']['import_file'] == str(ROOT / 'src/geosolver/__init__.py')
        assert result['engine']['source_hash'] == SOURCE
        assert result['problem_hash'] == problem_hash(GeometryProblem.model_validate(read(BASE / job['input'])))
        assert result['requested_resources'] == result['used_resources'] == {
            'time_limit_seconds': 180.0, 'cores': 1, 'seed': job['seed']}
    if artifact:
        assert receipt['worker_import_matches'] is True
        assert process['import_root'] == str(ROOT / 'src/geosolver')
        assert process['cpu_affinity'] == [receipt['cpu']]
        assert process['installed_dependencies'] == expected_dependencies
        assert receipt['cpu'] in [14, 15]
        assert artifact['answers'] == result['answers']
        assert artifact['numeric_feasible'] == diag['numeric_feasible']
        assert artifact['diagnostics']['pipeline_summary'] == summary
    # The public API uses null diagnostics on resource errors; the frozen
    # reader accepts an absent/empty mapping. Adapt only that wire shape,
    # retaining the original status and raw bytes. Never infer missing stages.
    null_diagnostics = result.get('diagnostics') is None
    outcome_input = result | {'diagnostics': {}} if null_diagnostics else result
    outcome = read_run_outcome({'solver_result': outcome_input})
    answers = _answer_keys(result)
    exact_records = summary.get('exact_candidate_records', [])
    verifications = summary.get('verification_records', [])
    verified = [v for v in verifications if v.get('verified') is True]
    coordinates = []
    seen = set()
    for v in verified:
        x = [finite_number(x) for x in v.get('values', [])]
        if x and canonical(x) not in seen:
            seen.add(canonical(x))
            coordinates.append(x)
    exacts = []
    seen = set()
    for e in exact_records:
        r = e['exact_result']
        item = {k: r.get(k) for k in ['exact_status', 'identification_method', 'polynomial_degree',
                  'minimal_polynomial', 'selected_exact_value', 'input_precision_dps', 'discovery_precision_dps']}
        if canonical(item) not in seen:
            seen.add(canonical(item))
            exacts.append(item)
    exact_assembly = summary.get('exact_assembly', {})
    stage = summary.get('search_staged_fallback', {})
    row = {**job, 'target': cases[job['id']]['variants'][job['kind']]['target'],
        'status': result.get('status', 'harness_error'), 'failure_stage': outcome['failure_stage'],
        'termination_reason': result.get('termination_reason'),
        'normal_completion': outcome['normal_completion'],
        'null_diagnostics_read_as_empty_mapping': null_diagnostics,
        'engine': result.get('engine'),
        'numeric_feasible': diag.get('numeric_feasible'),
        'exact_identified': diag.get('exact_identified'),
        'public_solved': result.get('status') == 'solved',
        'original_reference_matched': (outcome['normal_completion'] and answers == expected_keys[job['id']]) if job['kind'] == 'original' else None,
        'answer_set_keys': answers, 'answer_count': len(answers),
        'answer_expressions': sorted(set(artifact.get('exact_candidates', []))),
        'elapsed_seconds': result.get('elapsed_seconds'), 'wall_seconds': receipt.get('wall_seconds'),
        'cpu_seconds': process.get('cpu_seconds'), 'cpu': receipt.get('cpu'),
        'started_at_utc': receipt.get('started_at_utc'),
        'loadavg_start': receipt.get('loadavg_start'), 'loadavg_end': receipt.get('loadavg_end'),
        'phase_timings': diag.get('phase_timings', {}),
        'counters': diag.get('counters', {}),
        'selected_backend': diag.get('pipeline_backend'),
        'fallback_triggered': stage.get('triggered'), 'selected_stage': stage.get('selected_stage'),
        'staged_search': stage,
        'selected_search_evaluations': summary.get('search', {}).get('evaluation_count'),
        'refinement_attempted_count': summary.get('refinement', {}).get('attempted_count'),
        'refinement_converged_count': summary.get('refinement', {}).get('converged_count'),
        'numeric_feasible_count': exact_assembly.get('numeric_feasible_count'),
        'accepted_candidate_count': exact_assembly.get('accepted_count'),
        'verified_record_count': len(verified),
        'verification_statuses': dict(Counter(v.get('status') for v in verifications)),
        'verified_coordinates_float': coordinates,
        'verified_target_values': sorted(set(format(Decimal(str(v['answer_hp'])), '.31g')
                                            for v in verified if v.get('answer_hp') is not None)),
        'exact_identifications': exacts,
        'rejection_tags': diag.get('rejection_tags', []),
        'harness_error': receipt.get('harness_error'),
        'api_error': result.get('error'),
        'receipt_path': str(receipt_path), 'receipt_sha256': file_hash(receipt_path),
        'artifact_path': str(artifact_path) if artifact else None,
        'worker_dependencies_match_selection': True if artifact else None,
        'artifact_sha256': file_hash(artifact_path) if artifact else None}
    return row


def aggregate(rows):
    elapsed = [r['elapsed_seconds'] for r in rows if r['elapsed_seconds'] is not None]
    return {'n': len(rows), 'solved': sum(r['public_solved'] for r in rows),
        'numeric_feasible': sum(r['numeric_feasible'] is True for r in rows),
        'numeric_not_feasible': sum(r['numeric_feasible'] is False for r in rows),
        'numeric_unobserved': sum(r['numeric_feasible'] is None for r in rows),
        'exact_failure_with_numeric': sum(r['numeric_feasible'] is True and not r['public_solved'] for r in rows),
        'fallback_triggered': sum(r['fallback_triggered'] is True for r in rows),
        'status': dict(Counter(r['status'] for r in rows)),
        'elapsed_median': statistics.median(elapsed) if elapsed else None}


def compare_targets(rows, pairs, problems, excluded_ids=()):
    """Descriptive paired counts; exclusions are post-hoc sensitivity only."""
    rows = [r for r in rows if r['id'] not in excluded_ids]
    pairs = [p for p in pairs if p['id'] not in excluded_ids]
    complete = [p for p in problems if p['complete'] and p['id'] not in excluded_ids]
    by_key = {(r['id'], r['seed'], r['kind']): r for r in rows}
    losses = [p for p in pairs if p['solved_original'] and not p['solved_variant']]
    return {
        'excluded_ids': list(excluded_ids),
        'complete_problems': len(complete),
        'solved_pattern_seed_stable': sum(p['solved_pattern_seed_stable'] for p in complete),
        'status_varies_by_target_both_seeds': sum(p['status_varies_by_target_both_seeds'] for p in complete),
        'varies_by_target_both_seeds_and_same_pattern': sum(p['status_varies_by_target_both_seeds'] and p['solved_pattern_seed_stable'] for p in complete),
        'all_targets_solved_both_seeds': sum(p['all_targets_solved_both_seeds'] for p in complete),
        'by_seed': {str(seed): {
            'target_status_split': sum(len({by_key[(p['id'], seed, kind)]['public_solved'] for kind in KINDS}) > 1 for p in complete),
            'all_five_numeric_feasible': sum(all(by_key[(p['id'], seed, kind)]['numeric_feasible'] is True for kind in KINDS) for p in complete),
        } for seed in SEEDS},
        'by_target': {kind: {
            'matched_pairs': sum(p['kind'] == kind for p in pairs),
            'original_solved_variant_failed': sum(p['kind'] == kind and p['solved_original'] and not p['solved_variant'] for p in pairs),
            'original_failed_variant_solved': sum(p['kind'] == kind and not p['solved_original'] and p['solved_variant'] for p in pairs),
            'both_solved': sum(p['kind'] == kind and p['solved_original'] and p['solved_variant'] for p in pairs),
            'both_failed': sum(p['kind'] == kind and not p['solved_original'] and not p['solved_variant'] for p in pairs),
        } for kind in KINDS if kind != 'original'},
        'original_solved_variant_failed': len(losses),
        'of_those_numeric_feasible': sum(p['numeric_variant'] is True for p in losses),
        'of_those_numeric_unknown': sum(p['numeric_variant'] is None for p in losses),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--partial', action='store_true')
    opts = parser.parse_args()
    selection, jobs, audit = verify_inputs()
    done = {int(f.parent.name) for f in (RAW / 'runs').glob('*/receipt.json')}
    assert done <= {j['index'] for j in jobs}
    if not opts.partial:
        assert len(done) == len(jobs), f'Incomplete: {len(done)}/{len(jobs)}'
    from benchmarks.research_runner import _canonical_json, reference_expressions
    from geosolver.exact import describe_exact
    expected = {}
    cases = {c['id']: c for c in selection['cases']}
    for cid in cases:
        reference = read(BASE / 'references' / f'{cid}.json')
        values = reference['answer']
        if not isinstance(values, list):
            values = [values]
        expected[cid] = sorted({_canonical_json(describe_exact(value).canonical_key())
                               for expression in values for value in reference_expressions(str(expression))})
    rows = [summarize_run(job, cases, expected, selection['runtime_dependencies']) for job in jobs if job['index'] in done]
    by_key = {(r['id'], r['seed'], r['kind']): r for r in rows}
    problems = []
    for case in selection['cases']:
        cid = case['id']
        item = {'id': cid, 'pool': case['pool'], 'n_vars': case['n_vars'], 'kinds': {}}
        for kind in KINDS:
            group = [by_key[(cid, seed, kind)] for seed in SEEDS if (cid, seed, kind) in by_key]
            item['kinds'][kind] = {**aggregate(group), 'indices': [r['index'] for r in group],
                'statuses': [r['status'] for r in group],
                'times': [r['elapsed_seconds'] for r in group],
                'answer_counts': [r['answer_count'] for r in group],
                'answer_sets_agree': group[0]['answer_set_keys'] == group[1]['answer_set_keys'] if len(group) == 2 else None,
                'answer_sets_agree_when_both_solved': group[0]['answer_set_keys'] == group[1]['answer_set_keys'] if len(group) == 2 and all(r['public_solved'] for r in group) else None}
        complete = all((cid, seed, kind) in by_key for seed in SEEDS for kind in KINDS)
        item['complete'] = complete
        if complete:
            item['solved_pattern_seed_stable'] = all(by_key[(cid, SEEDS[0], kind)]['public_solved'] == by_key[(cid, SEEDS[1], kind)]['public_solved'] for kind in KINDS)
            item['status_varies_by_target_both_seeds'] = all(len({by_key[(cid, seed, kind)]['public_solved'] for kind in KINDS}) > 1 for seed in SEEDS)
            item['all_targets_solved_both_seeds'] = all(by_key[(cid, seed, kind)]['public_solved'] for kind in KINDS for seed in SEEDS)
        problems.append(item)
    pairs = []
    for row in rows:
        if row['kind'] == 'original':
            continue
        original = by_key.get((row['id'], row['seed'], 'original'))
        if not original:
            continue
        distances = [d for a in original['verified_coordinates_float'] for b in row['verified_coordinates_float']
                     if (d := coordinate_distance(a, b)) is not None]
        pairs.append({'id': row['id'], 'seed': row['seed'], 'kind': row['kind'],
            'original_index': original['index'], 'variant_index': row['index'],
            'solved_original': original['public_solved'], 'solved_variant': row['public_solved'],
            'numeric_original': original['numeric_feasible'], 'numeric_variant': row['numeric_feasible'],
            'elapsed_ratio': row['elapsed_seconds'] / original['elapsed_seconds'] if row['elapsed_seconds'] is not None and original['elapsed_seconds'] else None,
            'nearest_relative_coordinate_distance_float': min(distances) if distances else None})
    loads = [json.loads(line)['loadavg'][0] for line in (RAW / 'loadavg.jsonl').read_text().splitlines()]
    summary = {'created_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'complete': len(rows) == len(jobs), 'planned': len(jobs), **aggregate(rows),
        'by_target_seed': {f'{kind}/{seed}': aggregate([r for r in rows if r['kind'] == kind and r['seed'] == seed]) for kind in KINDS for seed in SEEDS},
        'by_target_pool': {f'{kind}/{pool}': aggregate([r for r in rows if r['kind'] == kind and r['pool'] == pool]) for kind in KINDS for pool in ['development', 'unseen_a', 'unseen_b']},
        'original_reference_matches': sum(r['original_reference_matched'] is True for r in rows),
        'original_reference_assessed': sum(r['kind'] == 'original' for r in rows),
        'missing_worker_artifact_indices': [r['index'] for r in rows if r['artifact_path'] is None],
        'engine_identities': [json.loads(x) for x in sorted({canonical(r['engine']) for r in rows if r['engine']})],
        'paired_comparisons_all': compare_targets(rows, pairs, problems),
        'paired_comparisons_excluding_two_known_nonunique_problems': compare_targets(rows, pairs, problems, ['AIME-2012-I-14', 'HMMT-2011-FEB-GUTS-01']),
        'exclusion_note': 'Post-hoc sensitivity excluding the two problems with explicit continuous target families. No proof of uniqueness for every remaining problem.',
        'loadavg_1m': {'min': min(loads), 'median': statistics.median(loads), 'max': max(loads), 'samples': len(loads)},
        'swapped_target_correctness': 'No independent full-set reference; public_solved is exact output, not an independently established correct-answer rate.',
        'coordinate_distance_note': 'Floating diagnostic only, using saved verified coordinates. Zero is not a mathematical proof of identical configurations.',
        'time_note': 'Public-return time, not first feasible-figure time; shared-machine load is not controlled.',
        'seed_note': 'External seeds 43101/43102 are fixed. Internal fallback uses five consecutive derived seeds, overlapping in four values; do not call the two runs fully independent.',
        'audit': audit}
    output = RAW / 'analysis-preview' if opts.partial else BASE
    save(output / 'analysis-summary.json', summary)
    save(output / 'per-run.json', rows)
    save(output / 'per-problem.json', problems)
    save(output / 'paired-effects.json', pairs)
    import csv
    fields = ['index', 'id', 'pool', 'kind', 'seed', 'status', 'numeric_feasible', 'exact_identified',
              'original_reference_matched', 'answer_count', 'elapsed_seconds', 'cpu_seconds',
              'fallback_triggered', 'selected_search_evaluations', 'numeric_feasible_count',
              'accepted_candidate_count', 'verified_record_count', 'failure_stage']
    with (output / 'per-run.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in rows)
    with (output / 'per-problem.csv').open('w', newline='') as stream:
        fields = ['id', 'pool', 'n_vars', 'complete', 'solved_pattern_seed_stable'] + [f'{kind}_solved_of_2' for kind in KINDS]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for problem in problems:
            writer.writerow({**{k: problem.get(k) for k in fields[:5]},
                **{f'{kind}_solved_of_2': problem['kinds'][kind]['solved'] if problem['kinds'][kind]['n'] == 2 else None for kind in KINDS}})
    print(json.dumps({k: summary[k] for k in ['complete', 'n', 'solved', 'numeric_feasible', 'original_reference_matches', 'loadavg_1m']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
