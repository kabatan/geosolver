"""Report saved Q38 results only. No solver invocation and no substitute grading."""
from __future__ import annotations

import collections
import csv
import io
import json
import math
from pathlib import Path
import shutil
import statistics

import stage2

BASE = Path(__file__).resolve().parent
ROOT = stage2.EXTERNAL
MODES = ['point_names', 'variable_order', 'condition_order', 'orders_combined', 'combined']
SEEDS = [380101, 380102, 380103]


def write_csv(path, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    payload = stream.getvalue()
    assert len(payload.encode()) < 4_900_000
    path.write_text(payload, encoding='utf-8', newline='')


def save(path, data):
    assert len(json.dumps(data, ensure_ascii=False).encode()) < 4_000_000
    stage2.save(path, data)
    assert path.stat().st_size < 4_900_000


def counter(rows, key):
    return dict(sorted(collections.Counter(str(row.get(key)) for row in rows).items()))


def source_counts(candidates):
    counts = collections.Counter()
    for candidate in candidates:
        source = candidate.get('source')
        if isinstance(source, dict):
            label = str(source.get('origin_phase')) + '/' + str(source.get('origin_backend'))
        else:
            label = str(source)
        counts[label] += 1
    return dict(sorted(counts.items()))


def positive(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def pair(original, variant):
    assessed = all(r['matched'] is not None for r in (original, variant))
    comparable = assessed and all(r['matched'] is True and positive(r['wall_seconds'])
                                  for r in (original, variant))
    ratio = variant['wall_seconds'] / original['wall_seconds'] if comparable else None
    delta = variant['wall_seconds'] - original['wall_seconds'] if comparable else None
    direction = ('slower' if ratio >= 3 and delta >= 2 else
                 'faster' if ratio <= 1 / 3 and delta <= -2 else 'below_threshold') if comparable else None
    return {
        'id': variant['id'], 'mode': variant['mode'], 'seed': variant['seed'],
        'original_matched': original['matched'], 'variant_matched': variant['matched'],
        'original_state': original['state'], 'variant_state': variant['state'],
        'correctness_discordant': original['matched'] != variant['matched'] if assessed else None,
        'original_wall_seconds': original['wall_seconds'], 'variant_wall_seconds': variant['wall_seconds'],
        'timing_comparable': bool(comparable), 'variant_over_original': ratio,
        'variant_minus_original_seconds': delta, 'large_timing_direction': direction,
        'original_capped_cost': original['capped_cost'], 'variant_capped_cost': variant['capped_cost'],
    }


def comparison(identifier, mode, pairs):
    complete = all(p['original_matched'] is not None and p['variant_matched'] is not None for p in pairs)
    orig = sum(p['original_matched'] is True for p in pairs) if complete else None
    variant = sum(p['variant_matched'] is True for p in pairs) if complete else None
    difference = variant - orig if complete else None
    comparable = sum(p['timing_comparable'] for p in pairs)
    faster = sum(p['large_timing_direction'] == 'faster' for p in pairs)
    slower = sum(p['large_timing_direction'] == 'slower' for p in pairs)
    time_decidable = complete and comparable >= 2
    return {
        'id': identifier, 'mode': mode, 'all_three_pairs_assessed': complete,
        'original_matched_count': orig, 'variant_matched_count': variant,
        'success_rate_difference': difference / 3 if complete else None,
        'A': abs(difference) >= 2 if complete else None,
        'A_direction': ('improved' if difference > 0 else 'worsened') if complete and abs(difference) >= 2 else None,
        'one_third_difference': abs(difference) == 1 if complete else None,
        'discordant_seed_count': sum(p['correctness_discordant'] is True for p in pairs) if complete else None,
        'timing_comparable_pairs': comparable,
        'timing_comparable': time_decidable,
        'large_faster_pairs': faster, 'large_slower_pairs': slower,
        'T': max(faster, slower) >= 2 if time_decidable else None,
        'T_direction': ('faster' if faster >= 2 else 'slower') if time_decidable and max(faster, slower) >= 2 else None,
        'timing_determination': ('determined' if time_decidable else
                                 'insufficient_successful_pairs' if complete else 'incomplete_assessments'),
        'seed_directions': ';'.join(f"{p['seed']}:{p['large_timing_direction'] or 'unavailable'}" for p in pairs),
        'original_mean_capped_cost': statistics.mean(p['original_capped_cost'] for p in pairs) if complete else None,
        'variant_mean_capped_cost': statistics.mean(p['variant_capped_cost'] for p in pairs) if complete else None,
    }


def main():
    lock_checks = {str(p): stage2.check_lock(p) for p in (BASE, stage2.INPUT)}
    plan = stage2.read(BASE / 'execution-plan.json')
    preflight = stage2.read(ROOT / 'preflight.json')
    start = stage2.read(ROOT / 'execution-start.json')
    receipts = [stage2.read(p) for p in sorted((ROOT / 'receipts').glob('*.json'))]
    assert not any(r['state'] in ('starting', 'running') for r in receipts), 'Do not report a live snapshot as final'
    receipt_by_batch = {r['batch']: r for r in receipts}
    rows, diagnostics, raw_manifest, batches = [], [], [], []
    for batch in plan['batches']:
        number = batch['batch']
        _, dest, _ = stage2.paths(number)
        assessment_path = dest / 'assessment.jsonl'
        assessment = {}
        if assessment_path.exists():
            for line in assessment_path.read_text().splitlines():
                item = json.loads(line)
                key = (item['case_id'], item['seed'])
                assert key not in assessment
                assessment[key] = item
        receipt = receipt_by_batch.get(number)
        batch_diagnostics = []
        for identifier in batch['case_ids']:
            path = dest / 'runs' / identifier / f"{batch['seed']}.json"
            a = assessment.get((identifier, batch['seed']))
            raw = stage2.read(path) if path.exists() else None
            result = (raw or {}).get('solver_result') or {}
            diag = result.get('diagnostics') or {}
            info = diag.get('process_info') or {}
            process = (raw or {}).get('process') or {}
            issues = (raw or {}).get('execution_contract_issues') or []
            matched = a['matched'] if a else None
            if issues:
                state = 'contract_invalid'
                assert matched is None
            elif a:
                state = 'assessed'
            elif raw:
                state = 'unassessed_batch_stopped'
            elif receipt:
                state = 'attempted_raw_missing'
            else:
                state = 'not_started'
            if a:
                assert matched in (True, False)
                assert positive(a['wall_seconds'])
            row = {
                'batch': number, 'block': batch['block'], 'id': identifier,
                'mode': batch['mode'], 'seed': batch['seed'], 'state': state,
                'matched': matched, 'assessment_available': a is not None,
                'solver_status': result.get('status'), 'contract_issues': ';'.join(issues),
                'wall_seconds': a['wall_seconds'] if a else None,
                'wall_seconds_ungraded': result.get('elapsed_seconds') if not a else None,
                'process_wall_seconds': process.get('elapsed_seconds'),
                'cpu_seconds': info.get('cpu_seconds'), 'assigned_cpu': process.get('assigned_cpu'),
                'process_actual_affinity': json.dumps(process['actual_affinity']) if process else None,
                'worker_affinity': json.dumps(info.get('cpu_affinity')) if info else None,
                'actual_import_root': info.get('import_root'), 'process_returncode': process.get('returncode'),
                'external_timeout': process.get('timed_out'), 'error': json.dumps(result.get('error')) if result.get('error') else None,
                'capped_cost': (min(a['wall_seconds'], 180) if matched else 180) if a else None,
                'raw_path': str(path) if raw else None, 'raw_bytes': path.stat().st_size if raw else None,
                'raw_sha256': stage2.sha(path) if raw else None,
            }
            rows.append(row)
            if raw:
                raw_manifest.append({'path': str(path), 'bytes': row['raw_bytes'], 'sha256': row['raw_sha256']})
                candidates = diag.get('candidate_records') or []
                summary = diag.get('pipeline_summary') or {}
                d = {
                    'case_id': identifier, 'mode': batch['mode'], 'seed': batch['seed'],
                    'state': state, 'matched': matched, 'answers_are_ungraded': not bool(a),
                    'returned_answers': result.get('answers'), 'error': result.get('error'),
                    'execution_contract_issues': issues, 'process': process, 'process_info': info,
                    'engine': result.get('engine'), 'phase_timings': diag.get('phase_timings'),
                    'counters': diag.get('counters'),
                    'candidate_source_counts': source_counts(candidates),
                    'accepted_candidate_source_counts': source_counts([c for c in candidates if c.get('accepted')]),
                    'search': summary.get('search'), 'refinement': summary.get('refinement'),
                    'exact_assembly': summary.get('exact_assembly'),
                    'staged_fallback': summary.get('search_staged_fallback'),
                    'answer_source_candidate_id': summary.get('answer_source_candidate_id'),
                }
                batch_diagnostics.append(d)
                diagnostics.append(d)
        if batch_diagnostics:
            save(BASE / 'diagnostics' / f'{number:03d}.json', batch_diagnostics)
        batches.append({'batch': number, 'mode': batch['mode'], 'seed': batch['seed'],
                        'state': receipt['state'] if receipt else 'not_started',
                        'started_at_utc': receipt.get('started_at_utc') if receipt else None,
                        'finished_at_utc': receipt.get('finished_at_utc') if receipt else None,
                        'error': receipt.get('error') if receipt else None})
    assert len(rows) == 840
    keyed = {(r['id'], r['mode'], r['seed']): r for r in rows}
    assert len(keyed) == 840
    selected = list(csv.DictReader((BASE / 'selection.csv').open()))
    pairs, comparisons, problems = [], [], []
    for selection in selected:
        identifier = selection['id']
        subset = [r for r in rows if r['id'] == identifier]
        per_mode = []
        for mode in MODES + ['original_repeat']:
            pp = [pair(keyed[identifier, 'original', seed], keyed[identifier, mode, seed]) for seed in SEEDS]
            pairs.extend(pp)
            c = comparison(identifier, mode, pp)
            comparisons.append(c)
            per_mode.append(c)
        main = per_mode[:-1]
        repeat = per_mode[-1]
        complete = all(c['all_three_pairs_assessed'] for c in per_mode)
        time_comparable = complete and any(c['timing_comparable'] for c in main)
        problems.append({
            **selection, 'planned_runs': 21,
            'attempted_runs': sum(r['state'] != 'not_started' for r in subset),
            'raw_runs': sum(r['raw_path'] is not None for r in subset),
            'assessed_runs': sum(r['assessment_available'] for r in subset),
            'matched_runs': sum(r['matched'] is True for r in subset),
            'unassessed_runs': sum(r['state'] == 'unassessed_batch_stopped' for r in subset),
            'unattempted_runs': sum(r['state'] == 'not_started' for r in subset),
            'all_21_assessed': complete,
            'A': any(c['A'] is True for c in main) if complete else None,
            'A_modes': ';'.join(c['mode'] for c in main if c['A'] is True),
            'T': any(c['T'] is True for c in main) if time_comparable else None,
            'T_modes': ';'.join(c['mode'] for c in main if c['T'] is True),
            'time_comparable': time_comparable,
            'one_third_comparisons': sum(c['one_third_difference'] is True for c in main) if complete else None,
            'discordant_seed_pairs': sum(c['discordant_seed_count'] for c in main) if complete else None,
            'repeat_A': repeat['A'], 'repeat_T': repeat['T'],
            'determination': 'complete_subset_only' if complete else 'incomplete',
        })
    strata = []
    for dimension, p_stratum in sorted({(p['dimension_stratum'], p['p_stratum']) for p in problems}):
        group = [p for p in problems if (p['dimension_stratum'], p['p_stratum']) == (dimension, p_stratum)]
        strata.append({'dimension_stratum': dimension, 'p_stratum': p_stratum, 'problems': len(group),
                       'assessed_runs': sum(p['assessed_runs'] for p in group),
                       'unassessed_runs': sum(p['unassessed_runs'] for p in group),
                       'unattempted_runs': sum(p['unattempted_runs'] for p in group),
                       'complete_problems': sum(p['all_21_assessed'] for p in group),
                       'observed_subset_A': sum(p['A'] is True for p in group),
                       'observed_subset_T': sum(p['T'] is True for p in group),
                       'full_stratum_determined': all(p['all_21_assessed'] for p in group)})
    mode_rows = []
    for mode in ['original'] + MODES + ['original_repeat']:
        subset = [r for r in rows if r['mode'] == mode]
        observed = [r for r in subset if r['assessment_available']]
        mode_rows.append({'mode': mode, 'planned': len(subset), 'assessed': len(observed),
                          'matched': sum(r['matched'] is True for r in observed),
                          'unassessed': sum(r['state'] == 'unassessed_batch_stopped' for r in subset),
                          'not_started': sum(r['state'] == 'not_started' for r in subset),
                          'success_wall_median_observed_only': statistics.median(r['wall_seconds'] for r in observed if r['matched']) if any(r['matched'] for r in observed) else None,
                          'mean_capped_cost_observed_only': statistics.mean(r['capped_cost'] for r in observed) if observed else None})
    loads = [{'at_utc': start['execution_started_at_utc'], 'loadavg': start['loadavg']}]
    for r in receipts:
        loads.extend({'at_utc': s['at_utc'], 'loadavg': s['loadavg']} for s in r.get('load_samples', []))
        loads.append({'at_utc': r['finished_at_utc'], 'loadavg': r['final_loadavg']})
    complete = len(receipts) == 210 and all(r['state'] == 'complete' for r in receipts)
    completed_problems = [p for p in problems if p['all_21_assessed']]
    old_archive = BASE / 'execution-records/invalid-attempt-20261023T164136Z/archive-manifest.json'
    result = {
        'task': 'Q38', 'status': 'complete' if complete else 'stopped_assessment_error',
        'generated_at_utc': stage2.now(), 'execution_started_at_utc': start['execution_started_at_utc'],
        'execution_stopped_at_utc': receipts[-1]['finished_at_utc'],
        'planned_runs': 840, 'planned_batches': 210, 'attempted_runs_after_repair': len(raw_manifest),
        'completed_batches': sum(r['state'] == 'complete' for r in receipts),
        'stopped_batches': sum(r['state'] == 'stopped' for r in receipts),
        'run_state_counts': counter(rows, 'state'),
        'assessed_runs': sum(r['assessment_available'] for r in rows),
        'graded_correct': sum(r['matched'] is True for r in rows),
        'graded_incorrect': sum(r['matched'] is False for r in rows),
        'raw_solver_status_counts': counter([r for r in rows if r['raw_path']], 'solver_status'),
        'original_invalid_attempt_runs': 4, 'original_invalid_attempt_archive': str(old_archive),
        'all_solver_invocations_including_original_invalid_attempt': len(raw_manifest) + 4,
        'A_count': sum(p['A'] is True for p in problems) if complete else None,
        'T_count': sum(p['T'] is True for p in problems) if complete else None,
        'A_fraction_of_40': sum(p['A'] is True for p in problems) / 40 if complete else None,
        'T_fraction_of_40': sum(p['T'] is True for p in problems) / 40 if complete else None,
        'predictions_tested': complete,
        'completed_subset_only': {'problems': len(completed_problems),
            'ids': [p['id'] for p in completed_problems],
            'A_count': sum(p['A'] is True for p in completed_problems),
            'T_count': sum(p['T'] is True for p in completed_problems),
            'time_comparable_problems': sum(p['time_comparable'] for p in completed_problems),
            'repeat_A_count': sum(p['repeat_A'] is True for p in completed_problems),
            'repeat_T_count': sum(p['repeat_T'] is True for p in completed_problems),
            'one_third_comparisons': sum(p['one_third_comparisons'] for p in completed_problems),
            'discordant_seed_pairs': sum(p['discordant_seed_pairs'] for p in completed_problems),
            'not_an_estimate_for_40_problems': True},
        'stop_reason': receipts[-1].get('error'),
        'no_solver_retry_after_stop': True, 'no_custom_grading': True,
        'observed_worker_import_roots': sorted({r['actual_import_root'] for r in rows if r['actual_import_root']}),
        'worker_import_root_observed_runs': sum(bool(r['actual_import_root']) for r in rows),
        'observed_contract_issues': counter([r for r in rows if r['contract_issues']], 'contract_issues'),
        'cpus': preflight['cpus'], 'topology': preflight['topology'],
        'load_samples': loads,
        'loadavg_min': [min(s['loadavg'][i] for s in loads) for i in range(3)],
        'loadavg_max': [max(s['loadavg'][i] for s in loads) for i in range(3)],
        'file_limit_bytes': 4900000, 'max_saved_raw_bytes': max(r['bytes'] for r in raw_manifest),
        'raw_manifest': raw_manifest, 'raw_data_root': str(ROOT / 'campaigns'),
        'raw_data_copied_to_repository': False, 'lock_checks_after_execution': lock_checks,
        'prediction_rules_selection_plan_solver_grader_runner_contract_changes': False,
    }
    for name, data in [('runs.csv', rows), ('pairs.csv', pairs), ('per-comparison.csv', comparisons),
                       ('per-problem.csv', problems), ('per-stratum.csv', strata),
                       ('per-mode.csv', mode_rows), ('batches.csv', batches)]:
        write_csv(BASE / name, data)
    save(BASE / 'results-summary.json', result)
    records = BASE / 'execution-records'
    for name in ['preflight.json', 'execution-start.json', 'environment-repair.json']:
        shutil.copy2(ROOT / name, records / name)
    for path in (ROOT / 'receipts').iterdir():
        if path.is_file():
            shutil.copy2(path, records / path.name)
    print(json.dumps({k: result[k] for k in ['status', 'run_state_counts', 'graded_correct',
                                            'graded_incorrect', 'completed_subset_only',
                                            'loadavg_min', 'loadavg_max', 'max_saved_raw_bytes']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
