"""Recompute small Q33 tables from archived results and fresh paired replays."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

OUT = Path(__file__).resolve().parent
ARCH = Path('/home/kabatan/work/solver-experiment/research-archives')
IMP = ARCH / '2026-09-08/snapshot/benchmarks/solver-improvement-results-20260907'
OLD = ARCH / '2026-09-08/local/benchmarks/local-evaluation/solver-improvement-20260907'
EVID = ARCH / 'solver-evidence'
SPEED = EVID / 'optimization-speed-20261011'
STUDY = EVID / 'solver-analysis'


def read(path):
    return json.loads(path.read_text())


def write(path, obj):
    data = json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
    assert len(data.encode()) < 5_000_000
    path.write_text(data)


def table(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def answer_keys(answers):
    return sorted((a['kind'], tuple(a['value']['minimal_polynomial']),
                   a['value']['real_root_index']) for a in answers)


EXPECTED = {
    'HMMT-2013-FEB-GEO-04': sorted([('algebraic', ('1', '1', '-1'), 1), ('algebraic', ('1', '-1', '-1'), 1)]),
    'HMMT-2011-FEB-ALGGEO-18': sorted([('algebraic', ('1', '-7'), 0), ('algebraic', ('11', '-35'), 0)]),
    'HMMT-2023-FEB-GEO-04': [('algebraic', ('1', '0', '-5'), 1)],
    'HMMT-2024-FEB-GEO-10': [('algebraic', ('5', '0', '-6642'), 1)],
}

rows, grouped, transitions = [], {}, []
for receipt in sorted((OUT / 'runs').glob('*.receipt.json')):
    r = read(receipt)
    assert r['returncode'] == 0 and not r['timed_out'], receipt
    artifact = receipt.with_name(receipt.name.replace('.receipt.json', '.json'))
    result = read(artifact)
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == r['artifact_sha256']
    d = result['diagnostics']
    summary = d['pipeline_summary']
    ledger = summary['candidate_ledger']
    keys = answer_keys(r['answers'])
    row = dict(experiment=r['group'], case=r['case'], seed=r['seed'], order_index=r['index'],
               arm='A' if r['index'] in (0, 3) else 'B', variant=r['variant'],
               wall_seconds=r['process_wall_seconds'], refinement_seconds=r['phase_timings']['refinement'],
               status=r['status'], answer_count=len(keys), matches_reference=keys == EXPECTED[r['case']],
               answers=json.dumps(keys), search_evaluations=summary['search']['evaluation_count'],
               hp_residual_evaluations=r['counters'].get('evaluate_hp_residual', 0),
               initial_ledger_sha256=digest(ledger), source_hash=r['engine']['source_hash'],
               artifact=str(artifact.relative_to(OUT)), artifact_sha256=r['artifact_sha256'])
    rows.append(row)
    grouped.setdefault((r['group'], r['case']), []).append((row, result))
table(OUT / 'replays.csv', rows)
summaries = []
for (group, case), items in sorted(grouped.items()):
    assert len(items) == 4 and {r['order_index'] for r, _ in items} == {0, 1, 2, 3}
    arms = {}
    for arm in ('A', 'B'):
        rr = [r for r, _ in items if r['arm'] == arm]
        arms[arm] = dict(mean_wall_seconds=statistics.mean(r['wall_seconds'] for r in rr),
                         mean_refinement_seconds=statistics.mean(r['refinement_seconds'] for r in rr),
                         answer_counts=[r['answer_count'] for r in rr],
                         reference_matches=[r['matches_reference'] for r in rr],
                         hp_residual_evaluations=[r['hp_residual_evaluations'] for r in rr],
                         same_answer_set_between_repeats=len({r['answers'] for r in rr}) == 1,
                         same_initial_ledger_between_repeats=len({r['initial_ledger_sha256'] for r in rr}) == 1)
    aa = next(v for r, v in items if r['order_index'] == 0)
    bb = next(v for r, v in items if r['order_index'] == 1)
    a_map = {c['candidate_id']: c for c in aa['diagnostics']['candidate_records']}
    b_map = {c['candidate_id']: c for c in bb['diagnostics']['candidate_records']}
    common = a_map.keys() & b_map.keys()
    summaries.append(dict(experiment=group, case=case, arms=arms,
                          mean_wall_ratio_B_over_A=arms['B']['mean_wall_seconds']/arms['A']['mean_wall_seconds'],
                          same_initial_ledger_between_arms=digest(aa['diagnostics']['pipeline_summary']['candidate_ledger'])
                          == digest(bb['diagnostics']['pipeline_summary']['candidate_ledger']),
                          common_selected_candidate_ids=len(common),
                          same_selected_source_records=(a_map.keys() == b_map.keys() and
                                                        all(a_map[k]['source'] == b_map[k]['source'] for k in common))))
    for k in sorted(common):
        a, b = a_map[k], b_map[k]
        stages = lambda c: json.dumps([':'.join(s.split(':')[:2]) for s in c['phase_history']])
        transitions.append(dict(experiment=group, case=case, candidate_id=k,
                                same_source=a['source'] == b['source'], before_accepted=a['accepted'],
                                after_accepted=b['accepted'], before_stages=stages(a), after_stages=stages(b)))
table(OUT / 'candidate-transitions.csv', transitions)
local = []
for p in sorted(OUT.glob('stability-local--*.json')):
    r = read(p)
    for row in r['rows']:
        local.append(dict(variant=r['variant'], epsilon=row['epsilon'], closure_dps=row['closure_dps'],
                          target_error_digits=float(row['target_error_digits_before_verification']),
                          default_verified=row['final_verified'], default_stop_dps=row['final_precision'],
                          high_verified=row['high_verified'], high_stop_dps=row['high_precision'],
                          high_failure_tags=';'.join(row['high_failure_tags']), seconds=row['seconds']))
table(OUT / 'stability.csv', local)
sample = [0.1, 0.2, 0.3]
write(OUT / 'replay-summary.json', dict(
    paired_cases=summaries, stability=local,
    rounding_example=dict(residuals=sample, hypot=math.hypot(*sample),
                          sqrt_sum_squares=math.sqrt(sum(x*x for x in sample)),
                          ulp_distance=abs(math.hypot(*sample)-math.sqrt(sum(x*x for x in sample)))/math.ulp(math.hypot(*sample))),
    completed_full_solves=len(rows), total_solve_process_wall=sum(r['wall_seconds'] for r in rows),
    setup_errors_not_solves=2,
    interpretation='Selected historical replay, no new-problem validation; elapsed time is shared-host time.'))

historic = {}
comparisons = {}
for name in ('cases.csv', 'rejected-stage8-cases.csv', 'rejected-stage11-cases.csv', 'rejected-stage12-cases.csv'):
    rr = list(csv.DictReader((IMP / name).open()))
    comparisons[name] = {(r['case_id'], r['seed']): r for r in rr}
    historic[name] = dict(runs=len(rr), before=sum(r['before_matched'] == 'True' for r in rr),
                         after=sum(r['after_matched'] == 'True' for r in rr),
                         changed=[r for r in rr if r['before_matched'] != r['after_matched']])
historic['reservation_stage11_to_12'] = [dict(case=k[0], seed=k[1],
                                            stage11=left['after_matched'], stage12=right['after_matched'])
    for k, left in comparisons['rejected-stage11-cases.csv'].items()
    if (right := comparisons['rejected-stage12-cases.csv'][k])['after_matched'] != left['after_matched']]
historic['norm_regression_subset'] = []
for arm in ('stage10-score', 'stage11-norm'):
    p = OLD / ('regression-'+arm) / 'assessment.jsonl'
    for line in p.open():
        r = json.loads(line)
        if r['case_id'] in ('HMMT-2011-FEB-ALGGEO-18', 'HMMT-2013-FEB-GEO-04'):
            historic['norm_regression_subset'].append(dict(arm=arm, case=r['case_id'], seed=r['seed'], matched=r['matched']))
historic['analytic_24'] = {k: v for k, v in read(SPEED / 'algebra-analytic-stable-v3-paired/comparison.json').items() if k != 'pairs'}
historic['same_source_changed_answer_count'] = []
for num, line in enumerate((SPEED / 'evaluation-slice-paired.jsonl').open(), 1):
    r = json.loads(line)
    if r['case'] == 'HMMT-2013-FEB-GEO-04' and r['variant'] == 'baseline-source':
        historic['same_source_changed_answer_count'].append(dict(line=num, repeat=r['repeat'],
                    source_hash=r['source_hash'], count=len(r['answers']), accepted_records=r['accepted_records']))
historic['same_source_94_repeat_counterexample_to_universal_instability'] = read(STUDY / 'analysis/detail-v1/summary.json')
optimization = list(csv.DictReader((EVID / 'optimization-20261011/final-paired-seed0.csv').open()))
historic['optimization_323'] = dict(faster=sum(float(r['delta_seconds']) < 0 for r in optimization),
                                    slower=sum(float(r['delta_seconds']) > 0 for r in optimization),
                                    jmo=[r for r in optimization if r['case_id'] == 'JMO-2017-PRE-10'])
write(OUT / 'historical-checks.json', historic)

log = subprocess.check_output(['git', '-C', '/home/kabatan/work/solver', 'log', '--all',
    '--format=%H%x00%ad%x00%s%x00%b%x1e', '--date=iso-strict', '--regexp-ignore-case',
    '--grep=regress\\|unexpected\\|不安定\\|なぜ\\|回帰', '--', 'src/geosolver', 'tests'], text=True)
commits = []
for raw in log.split('\x1e'):
    fields = raw.strip().split('\0', 3)
    if len(fields) == 4:
        commits.append(dict(zip(('commit', 'date', 'subject', 'body'), fields)))
write(OUT / 'git-history.json', commits)
print(json.dumps(dict(full_solves=len(rows), stability_arms=len(local), historical_commits=len(commits),
                      solve_process_seconds=sum(r['wall_seconds'] for r in rows)), ensure_ascii=False))
