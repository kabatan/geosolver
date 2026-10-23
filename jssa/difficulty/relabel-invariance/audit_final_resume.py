"""Audit Q38's registered stop and saved reports; never solve or grade."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'amendment-null-diagnostics'))
import support as s
import report_null_resume as report

ROOT = Path('/tmp/q38-null-diagnostics-authorized-resume')


def csv_rows(path):
    with path.open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    s.require(not args.output.exists(), 'Use a new audit path')
    guard = s.install_no_solver_guard(allow_processes=True)
    archive = BASE / 'execution-records/answer-at-amendment-65627f72.md'
    supplement = report.check_supplement_evidence(archive)
    original = {str(p): s.check_original_lock(p)
                for p in (BASE, s.CLEAN / 'jssa/difficulty/relabel-invariance')}
    patch = s.check_patch()
    git = lambda *argv: subprocess.check_output(['git', *argv], cwd=s.CLEAN, text=True).strip()
    s.require(git('rev-parse', 'HEAD') == s.EXECUTION_COMMIT, 'Execution commit changed')
    s.require(not git('status', '--porcelain', '--untracked-files=all'), 'Frozen checkout is dirty')
    s.require(not git('diff', s.FROZEN, '--', 'src', 'benchmarks/research_runner.py',
                      'benchmarks/cases.jsonl', 'pyproject.toml', 'uv.lock'), 'Frozen source changed')
    preserved = s.read(s.HERE / 'rescore-84/preserved-inputs.json')
    for name, entry in preserved['files'].items():
        path = s.EXTERNAL / name
        s.require(s.sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes'],
                  'Historical file changed: ' + name)
    seal = s.read(ROOT / 'adapter-seal.json')
    for name, key in [('authorization.json', 'authorization_sha256'),
                      ('recovery-021.json', 'recovery_sha256')]:
        s.require(s.sha(ROOT / name) == seal[key], 'Sealed receipt changed')
    s.require(s.sha(BASE / 'resume_null_stage2.py') == seal['implementation_sha256'],
              'Execution adapter changed')
    recovery = s.read(ROOT / 'recovery-021.json')
    s.require(recovery['state'] == 'complete' and recovery['solver_calls'] == 0,
              'Recovery was not solver-free and complete')
    s.require(s.inventory(Path(recovery['recovered_campaign'])) == recovery['outputs'],
              'Recovery outputs changed')
    s.require(s.sha(s.EXTERNAL / 'receipts/021.json') == recovery['original_stopped_receipt_sha256'],
              'Original batch-21 stop receipt changed')
    receipts = sorted((ROOT / 'receipts').glob('*.json'))
    records = [s.read(p) for p in receipts]
    expected = [(n, w) for n in range(22, 49) for w in (0, 1, 'final')] + [(49, 0), (49, 1)]
    s.require([(r['batch'], r.get('wave', 'final')) for r in records] == expected,
              'Unexpected run order or later batch')
    s.require(all(r['state'] == 'complete' for r in records[:-1]) and records[-1]['state'] == 'stopped',
              'Unexpected receipt state')
    for path, record in zip(receipts, records):
        s.require(s.sha(path) == s.sha(BASE / 'resume-records' / path.name), 'Receipt copy mismatch')
        if record['state'] == 'complete':
            s.require(s.inventory(Path(record['destination'])) == record['outputs'], 'Output inventory changed')
    for previous, current in zip(records, records[1:]):
        s.require(previous['finished_at_utc'] <= current['started_at_utc'], 'Execution steps overlapped')
    stop = s.read(BASE / 'resume-records/final-stop-diagnostic.json')
    s.require(records[-1]['returncode'] == 2 and '[Errno 27] File too large' in stop['stop_log'],
              'Stop reason differs')
    s.require(s.sha(ROOT / 'receipts/049.1.json') == stop['saved_stop_receipt_sha256'],
              'Stop receipt changed')
    s.require(s.sha(Path(stop['partial_outer_run_path'])) == stop['partial_outer_run_sha256']
              and Path(stop['partial_outer_run_path']).stat().st_size == 4_900_000, 'Partial output changed')
    for directory, inventory in stop['stopped_wave_inventories'].items():
        s.require(s.inventory(Path(directory)) == inventory, 'Stopped wave evidence changed')
    for number in (41, 46):
        event = s.read(BASE / 'resume-records' / f'orchestration-interruption-{number:03d}-0.json')
        receipt = ROOT / 'receipts' / f'{number:03d}.0.json'
        s.require(event['tool_command_exit_code'] == 143 and s.read(receipt)['state'] == 'complete'
                  and s.sha(receipt) == event['saved_receipt_sha256'], 'Interrupted command reconciliation changed')
    rows = csv_rows(BASE / 'final-report/runs.csv')
    aggregate = csv_rows(BASE / 'final-mode-counts/per-run.csv')
    keys = lambda r: (int(r['batch']), r.get('id', r.get('case_id')), int(r['seed']))
    planned = {(b['batch'], identifier, b['seed'])
               for b in s.plan()['batches'] for identifier in b['case_ids']}
    s.require(len(rows) == len(aggregate) == len(planned) == 840
              and {keys(r) for r in rows} == {keys(r) for r in aggregate} == planned,
              'The fixed 840-cell universe changed')
    aggregate_by_key = {keys(r): r for r in aggregate}
    for row in rows:
        other = aggregate_by_key[keys(row)]
        s.require(row['mode'] == other['mode'] and row['matched'] == other['matched']
                  and bool(row['raw_path']) == (other['raw_available'] == 'True')
                  and (row['state'] == 'assessed') == (other['assessment_available'] == 'True')
                  and row['raw_sha256'] == other['raw_sha256']
                  and row['worker_artifact_missing'] == other['worker_artifact_missing'],
                  'Independent aggregation disagrees')
        if row['raw_path']:
            s.require(s.sha(Path(row['raw_path'])) == row['raw_sha256'], 'Reported raw hash changed')
        if row['worker_artifact_missing'] == 'True':
            s.require(row['matched'] == 'False' and row['normal_completion'] == 'False'
                      and row['failure_stage'] == 'runtime', 'Artifact missing was not retained as incorrect')
        if row['state'] != 'assessed':
            s.require(row['matched'] == '' and row['capped_cost'] == '', 'Missing outcome was imputed')
    states = Counter(r['state'] for r in rows)
    s.require(dict(states) == {'assessed': 196, 'unassessed_saved_raw': 3,
                              'missing_outer_run_after_attempt': 1, 'unexecuted': 640},
              'Attempted/missing/unexecuted partition differs')
    s.require(sum(r['matched'] == 'True' for r in rows) == 161
              and sum(r['matched'] == 'False' for r in rows) == 35, 'Correct/incorrect count differs')
    modes = csv_rows(BASE / 'final-mode-counts/per-mode.csv')
    s.require(len(modes) == 7 and all(int(r['planned_denominator']) == 120
              and int(r['assessed_denominator']) == 28 and int(r['matched']) == 23
              and int(r['worker_artifact_missing']) == 3 and r['match_rate_all_120'] == '' for r in modes),
              'Incomplete mode denominator or missing-artifact count changed')
    summary = s.read(BASE / 'final-report/summary.json')
    s.require(summary['status'] == 'stopped_incomplete' and summary['A_count'] is None
              and summary['T_count'] is None and summary['complete_problem_count'] == 8
              and summary['complete_subset_A_count'] == summary['complete_subset_T_count'] == 0
              and summary['time_comparable_problems'] == 6, 'Partial results became full-plan claims')
    s.require(all(p['range_supported'] is None for p in summary['predictions']), 'Incomplete prediction judged')
    analysis_check = s.read(BASE / 'final-report/verification.json')
    s.require(analysis_check['status'] == 'passed'
              and analysis_check['analysis_sha256'] == s.sha(BASE / 'report_null_resume.py'),
              'Generated analysis differs from audited implementation')
    publication = s.read(BASE / 'resume-records/answer-publication.json')
    s.require(s.sha(BASE / 'answer.md') == publication['new_answer_sha256']
              and s.sha(archive) == publication['old_answer_sha256'], 'Published report version changed')
    max_bytes = max(p.stat().st_size for p in BASE.rglob('*') if p.is_file())
    s.require(max_bytes < 5_000_000, 'Repository artifact exceeds file size limit')
    s.check_guard(guard)
    output = {'status': 'passed', 'checked_at_utc': s.now(), 'solver_calls': 0, 'grading_calls': 0,
              'guard': guard, 'scope': 'Registered stopped run; not completion of the 840-trial plan',
              'original_locks': original, 'supplement_lock_with_verbatim_report_archive': supplement,
              'grader_patch': patch, 'frozen_checkout_clean': True, 'historical_files_unchanged': len(preserved['files']),
              'resume_steps': len(records), 'last_completed_batch': 48, 'stopped_batch': 49, 'stopped_wave': 1,
              'states': dict(states), 'matched': 161, 'incorrect': 35, 'worker_artifact_missing': 21,
              'aggregate_cross_check_rows': 840, 'complete_problems': 8,
              'complete_subset_A': 0, 'complete_subset_T_observed': 0, 'time_comparable_complete_problems': 6,
              'full_40_A_T_and_predictions': 'undetermined', 'max_repository_file_bytes': max_bytes,
              'answer_sha256': s.sha(BASE / 'answer.md'), 'audit_code_sha256': s.sha(Path(__file__)),
              'checks': ['original and supplement bytes', 'frozen checkout and grader', 'historical raw and stop preserved',
                         'completed prefix inventories and no overlap', 'outer-command interruption reconciliations',
                         'file-cap failure and partial file retained', '840-cell partition',
                         'independent immutable aggregation agrees', 'missing outcomes not imputed',
                         'partial A/T not reported as full-plan results', 'old and new answer versions retained']}
    s.save(args.output, output)
    print(json.dumps({k: output[k] for k in ('status', 'solver_calls', 'grading_calls', 'states',
                                          'matched', 'incorrect', 'full_40_A_T_and_predictions')}))


if __name__ == '__main__':
    main()
