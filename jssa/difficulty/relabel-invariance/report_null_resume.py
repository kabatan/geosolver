"""Read-only Q38 resumption analysis; no solving and no substitute grading.

Writes a new report directory. Original stopped reports and sealed evidence are
kept intact. Final answer.md is written separately after this audit succeeds.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'amendment-null-diagnostics'))
import support as s
import report_repaired as r

ROOT = Path('/tmp/q38-null-diagnostics-authorized-resume')
MODES = ['original', 'original_repeat', *r.MODES]


def write_csv(path, rows):
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    s.require(path.stat().st_size < 4_900_000, 'Report file exceeds limit')


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stopped', action='store_true')
    args = parser.parse_args()
    s.require(not args.output.exists(), 'Use a new report directory')
    guard = s.install_no_solver_guard()
    original_lock = s.check_original_lock(BASE)
    supplement_lock = s.check_supplement_lock()
    s.check_patch()
    preserved = s.read(s.HERE / 'rescore-84/preserved-inputs.json')
    for name, entry in preserved['files'].items():
        path = s.EXTERNAL / name
        s.require(s.sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes'],
                  'Historical input changed: ' + name)
    recovery = s.read(ROOT / 'recovery-021.json')
    s.require(recovery['state'] == 'complete' and recovery['solver_calls'] == 0, 'Recovery not complete')
    s.require(s.inventory(Path(recovery['recovered_campaign'])) == recovery['outputs'], 'Recovery output changed')
    all_receipts = [s.read(p) for p in sorted((ROOT / 'receipts').glob('*.json'))]
    s.require(not any(p['state'] in ('starting', 'running') for p in all_receipts),
              'Execution still active; do not make a final report')
    wave_receipts = [p for p in all_receipts if 'wave' in p]
    final_receipts = {p['batch']:p for p in all_receipts if 'wave' not in p}
    for previous, current in zip(wave_receipts, wave_receipts[1:]):
        s.require(previous['finished_at_utc'] <= current['started_at_utc'], 'Execution waves overlapped')
    expected_order = [(n, w) for n in range(22, 210) for w in (0, 1)]
    observed_order = [(p['batch'], p['wave']) for p in wave_receipts]
    s.require(observed_order == expected_order[:len(observed_order)], 'Wave order changed or skipped')
    for receipt in all_receipts:
        if receipt['state'] == 'complete':
            s.require(s.inventory(Path(receipt['destination'])) == receipt['outputs'], 'Receipt output hash mismatch')
    fully_complete = (len(final_receipts) == 188 and all(p['state'] == 'complete' for p in all_receipts))
    s.require(fully_complete or args.stopped, 'Incomplete execution requires --stopped')
    rows, diagnostics, manifests = [], [], []
    for batch in s.plan()['batches']:
        number = batch['batch']
        dest = s.destination(batch)
        assessment_dir = Path(recovery['recovered_campaign']) if number == 21 else dest
        assessments = {(a['case_id'], a['seed']):a for a in load_rows(assessment_dir / 'assessment.jsonl')}
        expected = {(i, batch['seed']) for i in batch['case_ids']}
        s.require(set(assessments) <= expected, 'Unplanned assessment')
        batch_diag = []
        for identifier in batch['case_ids']:
            path = dest / 'runs' / identifier / f"{batch['seed']}.json"
            # An interrupted wave can have saved raw data before batch assembly.
            if not path.exists() and number >= 22:
                part = 0 if identifier in batch['case_ids'][:3] else 1
                wave_path = ROOT / 'waves' / f'{number:03d}-{part}' / 'runs' / identifier / path.name
                if wave_path.exists():
                    path = wave_path
            raw = s.read(path) if path.exists() else None
            assessment = assessments.get((identifier, batch['seed']))
            result = (raw or {}).get('solver_result') or {}
            diag = result.get('diagnostics') or {}
            info = diag.get('process_info') or {}
            process = (raw or {}).get('process') or {}
            missing = ((result.get('error') or {}).get('code') == 'artifact_missing') if raw else None
            matched = assessment['matched'] if assessment else None
            if raw:
                s.require(raw['case_id'] == identifier and raw['seed'] == batch['seed'], 'Raw key mismatch')
                s.require(raw['source_hash'] == s.SOURCE_HASH, 'Raw source mismatch')
                s.require(raw['config']['time_limit_seconds'] == 180 and raw['config']['cores'] == 1,
                          'Raw resource contract mismatch')
                if fully_complete:
                    s.require(not raw['execution_contract_issues'], 'Contract violation in completed plan')
                if info:
                    s.require(info['import_root'] == str(s.CLEAN / 'src/geosolver'), 'Worker import mismatch')
                    s.require(info['cpu_affinity'] == process['actual_affinity'], 'Worker affinity mismatch')
                manifests.append({'batch':number, 'id':identifier, 'mode':batch['mode'], 'seed':batch['seed'],
                                  'path':str(path), 'bytes':path.stat().st_size, 'sha256':s.sha(path)})
            if assessment:
                s.require(raw is not None and type(matched) is bool, 'Assessment without raw or boolean result')
                if missing:
                    s.require(matched is False and not assessment['normal_completion']
                              and assessment['failure_stage'] == 'runtime', 'Missing worker must be incorrect')
            wall = assessment['wall_seconds'] if assessment else None
            cost = (min(wall, 180) if matched else 180) if assessment else None
            row = {'batch':number, 'id':identifier, 'mode':batch['mode'], 'seed':batch['seed'],
                   'state':'assessed' if assessment else 'unassessed_saved_raw' if raw else 'no_raw',
                   'matched':matched, 'wall_seconds':wall, 'capped_cost':cost,
                   'worker_artifact_missing':missing,
                   'diagnostics_null': result.get('diagnostics', {}) is None if raw else None,
                   'status':assessment['status'] if assessment else result.get('status'),
                   'failure_stage':assessment.get('failure_stage') if assessment else None,
                   'normal_completion':assessment.get('normal_completion') if assessment else None,
                   'error_code':(result.get('error') or {}).get('code'),
                   'cpu_seconds':assessment.get('cpu_seconds') if assessment else None,
                   'peak_rss_bytes':assessment.get('peak_rss_bytes') if assessment else None,
                   'worker_import_root':info.get('import_root'), 'assigned_cpu':process.get('assigned_cpu'),
                   'external_timeout':process.get('timed_out'),
                   'raw_path':str(path) if raw else None,
                   'raw_sha256':s.sha(path) if raw else None,
                   'assessment_path':str(assessment_dir / 'assessment.jsonl') if assessment else None}
            rows.append(row)
            if raw:
                pipeline = diag.get('pipeline_summary') or {}
                candidates = diag.get('candidate_records') or []
                batch_diag.append({'id':identifier, 'mode':batch['mode'], 'seed':batch['seed'],
                                   'matched':matched, 'worker_artifact_missing':missing,
                                   'phase_timings':diag.get('phase_timings'), 'counters':diag.get('counters'),
                                   'candidate_source_counts':r.source_counts(candidates),
                                   'accepted_candidate_source_counts':r.source_counts([c for c in candidates if c.get('accepted')]),
                                   'search':pipeline.get('search'), 'refinement':pipeline.get('refinement'),
                                   'exact_assembly':pipeline.get('exact_assembly'),
                                   'answer_source_candidate_id':pipeline.get('answer_source_candidate_id')})
        if batch_diag:
            diagnostics.append((number, batch_diag))
    s.require(len(rows) == 840, 'Fixed denominator changed')
    keyed = {(x['id'],x['mode'],x['seed']):x for x in rows}
    s.require(len(keyed) == 840, 'Duplicate planned cell')
    if fully_complete:
        s.require(len(manifests) == 840 and all(x['matched'] is not None for x in rows), 'Incomplete final data')
    selections = list(csv.DictReader((BASE / 'selection.csv').open()))
    pairs, comparisons, problems = [], [], []
    for selection in selections:
        identifier = selection['id']
        subset = [x for x in rows if x['id'] == identifier]
        cs = []
        for mode in r.MODES + ['original_repeat']:
            pp = [r.pair(keyed[identifier,'original',seed], keyed[identifier,mode,seed]) for seed in r.SEEDS]
            pairs.extend(pp)
            c = r.comparison(identifier, mode, pp)
            comparisons.append(c)
            cs.append(c)
        main_cs, repeat = cs[:-1], cs[-1]
        complete = all(c['all_three_pairs_assessed'] for c in cs)
        comparable = complete and any(c['timing_comparable'] for c in main_cs)
        problems.append({**selection, 'assessed_runs':sum(x['matched'] is not None for x in subset),
                         'correct_runs':sum(x['matched'] is True for x in subset),
                         'worker_artifact_missing':sum(x['worker_artifact_missing'] is True for x in subset),
                         'all_21_assessed':complete,
                         'A':any(c['A'] is True for c in main_cs) if complete else None,
                         'A_modes':';'.join(c['mode'] for c in main_cs if c['A'] is True),
                         'A_improved':any(c['A_direction'] == 'improved' for c in main_cs) if complete else None,
                         'A_worsened':any(c['A_direction'] == 'worsened' for c in main_cs) if complete else None,
                         'T':any(c['T'] is True for c in main_cs) if comparable else None,
                         'T_modes':';'.join(c['mode'] for c in main_cs if c['T'] is True),
                         'time_comparable':comparable,
                         'repeat_A':repeat['A'], 'repeat_T':repeat['T'],
                         'repeat_time_comparable':repeat['timing_comparable']})
    strata = []
    for dimension, p_stratum in sorted({(p['dimension_stratum'],p['p_stratum']) for p in problems}):
        ps = [p for p in problems if (p['dimension_stratum'],p['p_stratum']) == (dimension,p_stratum)]
        strata.append({'dimension_stratum':dimension, 'p_stratum':p_stratum, 'problems':len(ps),
                       'complete_problems':sum(p['all_21_assessed'] for p in ps),
                       'A_observed':sum(p['A'] is True for p in ps), 'T_observed':sum(p['T'] is True for p in ps),
                       'time_comparable_problems':sum(p['time_comparable'] for p in ps),
                       'worker_artifact_missing':sum(p['worker_artifact_missing'] for p in ps)})
    mode_rows = []
    for mode in MODES:
        subset = [x for x in rows if x['mode'] == mode]
        assessed = [x for x in subset if x['matched'] is not None]
        success_walls = [x['wall_seconds'] for x in assessed if x['matched'] and r.positive(x['wall_seconds'])]
        missing = sum(x['worker_artifact_missing'] is True for x in subset)
        mode_rows.append({'mode':mode, 'planned_denominator':120, 'raw_received':sum(x['raw_path'] is not None for x in subset),
                          'assessed_denominator':len(assessed), 'matched':sum(x['matched'] is True for x in assessed),
                          'incorrect':sum(x['matched'] is False for x in assessed),
                          'worker_artifact_missing':missing,
                          'worker_artifact_missing_fraction_of_120':missing / 120 if fully_complete else None,
                          'diagnostics_null':sum(x['diagnostics_null'] is True for x in subset),
                          'mean_capped_cost':statistics.mean(x['capped_cost'] for x in assessed) if assessed else None,
                          'success_wall_median':statistics.median(success_walls) if success_walls else None,
                          'cpu_observed_count':sum(x['cpu_seconds'] is not None for x in assessed),
                          'rss_observed_count':sum(x['peak_rss_bytes'] is not None for x in assessed)})
    main_comparisons = [c for c in comparisons if c['mode'] != 'original_repeat']
    main_pairs = [p for p in pairs if p['mode'] != 'original_repeat']
    A = sum(p['A'] is True for p in problems) if fully_complete else None
    T = sum(p['T'] is True for p in problems) if fully_complete else None
    time_count = sum(p['time_comparable'] for p in problems)
    point = [c for c in comparisons if c['mode'] == 'point_names']
    point_A = sum(c['A'] is True for c in point) if fully_complete else None
    point_T = sum(c['T'] is True for c in point) if fully_complete else None
    variable_T_ids = {c['id'] for c in comparisons if c['mode'] in ('variable_order','orders_combined','combined') and c['T'] is True}
    predictions = [
        {'prediction':'P1', 'fixed_range':'A=0..4/40; point=2', 'observed':A,
         'range_supported':0 <= A <= 4 if fully_complete else None, 'point_prediction_met':A == 2 if fully_complete else None},
        {'prediction':'P2', 'fixed_range':'T=12..20/40; point=16', 'observed':T,
         'range_supported':12 <= T <= 20 if fully_complete else None, 'point_prediction_met':T == 16 if fully_complete else None},
        {'prediction':'P3', 'fixed_range':'point_names A=0 and T=0..2', 'observed':f'A={point_A},T={point_T}' if fully_complete else None,
         'range_supported':point_A == 0 and 0 <= point_T <= 2 if fully_complete else None, 'point_prediction_met':None},
        {'prediction':'secondary', 'fixed_range':'variable-order modes cover at least 2/3 of T problems; T=0 fails',
         'observed':f'{len(variable_T_ids)}/{T}' if fully_complete else None,
         'range_supported':bool(T and len(variable_T_ids)*3 >= T*2) if fully_complete else None, 'point_prediction_met':None},
    ]
    old_receipts = [s.read(p) for p in sorted((s.EXTERNAL / 'receipts').glob('*.json'))]
    loads = [v['loadavg'] for p in old_receipts + wave_receipts for v in p.get('load_samples', [])]
    # Independently check thresholds in the generated pairs and comparisons.
    for p in pairs:
        if p['timing_comparable']:
            x, y = p['original_wall_seconds'], p['variant_wall_seconds']
            expected = 'slower' if y >= 3*x and y-x >= 2 else 'faster' if x >= 3*y and x-y >= 2 else 'below_threshold'
            s.require(p['large_timing_direction'] == expected, 'Paired timing threshold disagreement')
            s.require(math.isclose(p['variant_over_original'], y/x, rel_tol=1e-14), 'Timing ratio mismatch')
        else:
            s.require(p['variant_over_original'] is None and p['large_timing_direction'] is None,
                      'A failed or missing pair was compared as a fast answer')
    for c in comparisons:
        pp = [p for p in pairs if (p['id'],p['mode']) == (c['id'],c['mode'])]
        if c['all_three_pairs_assessed']:
            difference = sum(p['variant_matched'] for p in pp) - sum(p['original_matched'] for p in pp)
            s.require(c['A'] == (abs(difference) >= 2), 'A threshold mismatch')
        if c['timing_comparable']:
            directions = Counter(p['large_timing_direction'] for p in pp)
            s.require(c['T'] == (max(directions['faster'], directions['slower']) >= 2), 'T direction mismatch')
    s.check_guard(guard)
    summary = {'status':'complete' if fully_complete else 'stopped_incomplete', 'generated_at_utc':s.now(),
               'analysis_solver_calls':0, 'analysis_grading_calls':0,
               'planned_runs':840, 'raw_received':len(manifests),
               'assessed_runs':sum(x['matched'] is not None for x in rows),
               'matched':sum(x['matched'] is True for x in rows),
               'incorrect':sum(x['matched'] is False for x in rows),
               'new_raw_since_resume':sum(x['batch'] >= 22 for x in manifests),
               'recovered_batch_21':{'assessed':4,'matched':recovery['summary']['matched_count'],'solver_calls':0},
               'worker_artifact_missing':sum(x['worker_artifact_missing'] is True for x in rows),
               'A_count':A,'T_count':T,'A_fraction_of_40':A/40 if fully_complete else None,
               'T_fraction_of_40':T/40 if fully_complete else None,
               'time_comparable_problems':time_count,'time_incomparable_problems':40-time_count if fully_complete else None,
               'T_fraction_of_comparable':T/time_count if fully_complete and time_count else None,
               'repeat_A_count':sum(p['repeat_A'] is True for p in problems) if fully_complete else None,
               'repeat_T_count':sum(p['repeat_T'] is True for p in problems) if fully_complete else None,
               'repeat_time_comparable_problems':sum(p['repeat_time_comparable'] for p in problems),
               'A_improved_problems':sum(p['A_improved'] is True for p in problems) if fully_complete else None,
               'A_worsened_problems':sum(p['A_worsened'] is True for p in problems) if fully_complete else None,
               'one_third_comparisons':sum(c['one_third_difference'] is True for c in main_comparisons),
               'discordant_seed_pairs':sum(p['correctness_discordant'] is True for p in main_pairs),
               'point_names_A':point_A,'point_names_T':point_T,'variable_order_T_problem_count':len(variable_T_ids),
               'predictions':predictions, 'complete_problem_count':sum(p['all_21_assessed'] for p in problems),
               'worker_import_observed_count':sum(bool(x['worker_import_root']) for x in rows),
               'worker_import_roots':sorted({x['worker_import_root'] for x in rows if x['worker_import_root']}),
               'loadavg_min':[min(x[i] for x in loads) for i in range(3)],
               'loadavg_max':[max(x[i] for x in loads) for i in range(3)],
               'max_raw_bytes':max(x['bytes'] for x in manifests), 'raw_external_root':str(s.EXTERNAL),
               'resumption_external_root':str(ROOT), 'original_lock':original_lock, 'supplement_lock':supplement_lock,
               'original_308_files_unchanged':True, 'max_new_parallel_solves':3,
               'observed_max_wave_command_seconds':max((x.get('elapsed_seconds',0) for x in wave_receipts),default=0),
               'stopped_receipts':[{'batch':x['batch'],'wave':x.get('wave'),'error':x.get('error')} for x in all_receipts if x['state'] == 'stopped'],
               'limitations':'Three seeds, five transformation comparisons, selected development sample, shared CPU load; '
               'no retries, no causal identification of artifact-missing failures, missing diagnostic metrics are not zero.'}
    args.output.mkdir(parents=True)
    (args.output / 'diagnostics').mkdir()
    for name, data in [('runs.csv',rows),('pairs.csv',pairs),('per-comparison.csv',comparisons),
                       ('per-problem.csv',problems),('per-stratum.csv',strata),('per-mode.csv',mode_rows),
                       ('fixed-predictions.csv',predictions),('raw-manifest.csv',manifests)]:
        write_csv(args.output / name, data)
    diagnostic_index = []
    for number, data in diagnostics:
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
        path = args.output / 'diagnostics' / f'{number:03d}.json'
        if len(payload.encode()) >= 4_900_000:
            path = ROOT / 'large-report-diagnostics' / args.output.name / f'{number:03d}.json'
            path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as stream:
            stream.write(payload)
        diagnostic_index.append({'batch':number,'path':str(path),'bytes':path.stat().st_size,'sha256':s.sha(path)})
    write_csv(args.output / 'diagnostic-index.csv', diagnostic_index)
    s.save(args.output / 'summary.json', summary)
    s.save(args.output / 'verification.json', {'status':'passed','checked_at_utc':s.now(),'solver_calls':0,
           'grading_calls':0,'guard':guard,'analysis_sha256':s.sha(Path(__file__)),
           'checks':['original and supplement locks','historical 308 files unchanged','recovery and wave hashes',
                     'fixed prefix order and no wave overlap','840 unique cells','artifact_missing retained as incorrect',
                     'paired successful times only','independent A/T arithmetic'],
           'scope':'Full fixed-plan analysis' if fully_complete else 'Stopped execution, no full-plan A/T claims'})
    s.require(max(p.stat().st_size for p in args.output.rglob('*') if p.is_file()) < 5_000_000,
              'Report output exceeds repository size limit')
    print(json.dumps({k:summary[k] for k in ['status','raw_received','assessed_runs','matched','incorrect',
                                           'worker_artifact_missing','A_count','T_count','time_comparable_problems',
                                           'repeat_A_count','repeat_T_count','stopped_receipts']},ensure_ascii=False))


if __name__ == '__main__':
    main()
