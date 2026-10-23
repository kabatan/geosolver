"""Read saved raw/assessment files only; retain artifact-missing trials per mode.

Never infer correctness from raw status. Optional assessment-root holds recovered
assessments under the original campaign basename, without replacing old evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from support import (EXTERNAL, check_guard, destination, install_no_solver_guard,
                     now, plan, read, require, save, sha)

MODES = ['original', 'original_repeat', 'point_names', 'variable_order',
         'condition_order', 'orders_combined', 'combined']


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaigns', type=Path, default=EXTERNAL / 'campaigns')
    parser.add_argument('--assessment-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Use a new output directory; preserve previous reports')
    guard = install_no_solver_guard()
    rows = []
    for batch in plan()['batches']:
        dest = destination(batch, args.campaigns)
        assessment_path = dest / 'assessment.jsonl'
        if args.assessment_root:
            overlay = args.assessment_root / dest.name / 'assessment.jsonl'
            if overlay.exists():
                require(not assessment_path.exists() or sha(overlay) == sha(assessment_path),
                        'Overlay may not change an existing assessment')
                assessment_path = overlay
        assessed = {}
        if assessment_path.exists():
            for line in assessment_path.read_text(encoding='utf-8').splitlines():
                item = json.loads(line)
                key = (item['case_id'], item['seed'])
                require(key not in assessed, 'Duplicate assessment')
                assessed[key] = item
        expected = {(identifier, batch['seed']) for identifier in batch['case_ids']}
        require(set(assessed) <= expected, 'Unplanned assessment')
        for identifier in batch['case_ids']:
            path = dest / 'runs' / identifier / f"{batch['seed']}.json"
            raw = read(path) if path.exists() else None
            result = (raw or {}).get('solver_result') or {}
            error = result.get('error') or {}
            # Frozen EngineRunner's artifact_missing code is the positive evidence.
            # A missing outer run JSON or null diagnostics alone is not that evidence.
            missing = error.get('code') == 'artifact_missing'
            null_diagnostics = bool(result) and result.get('diagnostics', {}) is None
            item = assessed.get((identifier, batch['seed']))
            if raw is not None:
                require(raw['case_id'] == identifier and raw['seed'] == batch['seed'], 'Raw key mismatch')
            if item is not None:
                require(raw is not None, 'Assessment without a raw artifact')
                require(item['matched'] is True or item['matched'] is False, 'Unverified assessment')
                if missing:
                    require(item['matched'] is False, 'Artifact-missing trial must count incorrect')
            rows.append({'batch': batch['batch'], 'mode': batch['mode'], 'case_id': identifier,
                         'seed': batch['seed'], 'raw_available': raw is not None,
                         'assessment_available': item is not None,
                         'matched': item['matched'] if item is not None else None,
                         'diagnostics_null': null_diagnostics if raw is not None else None,
                         'worker_artifact_missing': missing if raw is not None else None,
                         'runtime_status': result.get('status'), 'error_code': error.get('code'),
                         'raw_sha256': sha(path) if raw is not None else None,
                         'assessment_sha256': sha(assessment_path) if item is not None else None})
    require(len(rows) == 840, 'Fixed denominator must remain 840')
    modes = []
    for mode in MODES:
        subset = [r for r in rows if r['mode'] == mode]
        observed = [r for r in subset if r['raw_available']]
        assessed = [r for r in subset if r['assessment_available']]
        missing = sum(r['worker_artifact_missing'] is True for r in observed)
        correct = sum(r['matched'] is True for r in assessed)
        require(len(subset) == 120, 'Each mode must have 120 fixed trials')
        modes.append({'mode': mode, 'planned_denominator': len(subset), 'raw_received': len(observed),
                      'assessed_denominator': len(assessed), 'matched': correct,
                      'incorrect': len(assessed) - correct,
                      'unassessed_raw': len(observed) - len(assessed),
                      'raw_not_available': len(subset) - len(observed),
                      'worker_artifact_missing': missing,
                      'worker_artifact_missing_assessed_incorrect': sum(
                          r['worker_artifact_missing'] is True and r['matched'] is False for r in assessed),
                      'worker_artifact_missing_unassessed': sum(
                          r['worker_artifact_missing'] is True and not r['assessment_available'] for r in observed),
                      'diagnostics_null': sum(r['diagnostics_null'] is True for r in observed),
                      'missing_rate_among_raw_received': missing / len(observed) if observed else None,
                      'match_rate_assessed_subset_only': correct / len(assessed) if assessed else None,
                      'match_rate_all_120': correct / 120 if len(assessed) == 120 else None})
    check_guard(guard)
    args.output.mkdir(parents=True)
    write_csv(args.output / 'per-run.csv', rows)
    write_csv(args.output / 'per-mode.csv', modes)
    save(args.output / 'summary.json', {
        'generated_at_utc': now(), 'solver_calls': 0, 'grading_calls': 0, 'guard': guard,
        'planned_denominator': len(rows), 'raw_received': sum(r['raw_available'] for r in rows),
        'assessed_denominator': sum(r['assessment_available'] for r in rows),
        'worker_artifact_missing': sum(r['worker_artifact_missing'] is True for r in rows),
        'all_trials_assessed': all(r['assessment_available'] for r in rows),
        'rule': 'Every artifact_missing trial remains in its original mode/seed denominator. '
                'When assessed it must be incorrect; pending raw files remain unassessed until authorized.',
        'interpretation': 'Report mode imbalance as an outcome, without deleting, replacing or retrying '
                          'these trials. Runtime artifacts alone do not establish a mathematical failure cause.'})
    print({'raw': sum(r['raw_available'] for r in rows),
           'assessed': sum(r['assessment_available'] for r in rows),
           'worker_artifact_missing': sum(r['worker_artifact_missing'] is True for r in rows),
           'solver_calls': 0, 'grading_calls': 0})


if __name__ == '__main__':
    main()
