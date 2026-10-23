"""Check null handling and the denominator with synthetic records, no solver."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from support import (SOURCE_HASH, canonical, check_guard, install_no_solver_guard,
                     load_grader, now, read, require, save)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Use a new evidence path')
    guard = install_no_solver_guard()
    grader = load_grader()
    from geosolver.exact import describe_exact
    config = {'seeds': [0], 'time_limit_seconds': 180, 'cores': 1,
              'thread_environment': grader.THREAD_ENVIRONMENT}
    common = {'source_hash': SOURCE_HASH, 'dependency_lock_hash': 'synthetic-only', 'config': config}
    cases = [{'id': identifier, 'dsl': {}, 'dsl_path': 'unused.json', 'answer': ['1'],
              'truth_status': 'verified', 'authoring_status': 'runnable'}
             for identifier in ['synthetic-null', 'synthetic-success']]
    reference_hash = hashlib.sha256(canonical(['1'])).hexdigest()
    manifest = common | {'cases': [
        {'id': row['id'], 'problem_hash': 'synthetic-only', 'truth_status': 'verified',
         'authoring_status': 'runnable', 'reference_hash': reference_hash} for row in cases]}
    null_result = {'status': 'engine_error', 'answers': [], 'diagnostics': None,
                   'error': {'code': 'artifact_missing', 'message': 'synthetic worker artifact missing'},
                   'elapsed_seconds': 1.0, 'termination_reason': 'engine_failed'}
    null_raw = common | {'case_id': 'synthetic-null', 'seed': 0, 'problem_hash': 'synthetic-only',
                         'process': {'returncode': 2, 'timed_out': False, 'elapsed_seconds': 1.1},
                         'solver_result': null_result}
    empty_raw = null_raw | {'solver_result': null_result | {'diagnostics': {}}}
    omitted_raw = null_raw | {'solver_result': {k: v for k, v in null_result.items() if k != 'diagnostics'}}
    require(grader.read_run_outcome(null_raw) == grader.read_run_outcome(empty_raw)
            == grader.read_run_outcome(omitted_raw), 'Null/empty/omitted diagnostics differ')
    success_raw = common | {'case_id': 'synthetic-success', 'seed': 0, 'problem_hash': 'synthetic-only',
                            'process': {'returncode': 0, 'timed_out': False, 'elapsed_seconds': 1.1},
                            'solver_result': {'status': 'solved', 'elapsed_seconds': 1.0,
                                              'answers': [describe_exact('1').model_dump(mode='json')],
                                              'diagnostics': {}}}
    with tempfile.TemporaryDirectory(prefix='q38-synthetic-null-contract-') as temporary:
        root = Path(temporary)
        (root / 'cases.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in cases))
        campaign = root / 'campaign'
        save(campaign / 'campaign-manifest.json', manifest)
        for raw in [null_raw, success_raw]:
            save(campaign / 'runs' / raw['case_id'] / '0.json', raw)
        grader.assess_campaign(campaign, cases_path=root / 'cases.jsonl')
        grader.summarize_campaign(campaign)
        rows = [json.loads(line) for line in (campaign / 'assessment.jsonl').read_text().splitlines()]
        summary = read(campaign / 'summary.json')
        null_assessment = next(r for r in rows if r['case_id'] == 'synthetic-null')
        require(null_assessment['matched'] is False and null_assessment['failure_stage'] == 'runtime',
                'Artifact-missing fixture must be incorrect')
        require(summary['run_count'] == summary['assessed_count'] == 2
                and summary['matched_count'] == 1 and summary['match_rate'] == 0.5,
                'Artifact-missing fixture was excluded from the denominator')
    check_guard(guard)
    save(args.output, {'checked_at_utc': now(), 'status': 'passed', 'solver_calls': 0,
                       'guard': guard, 'synthetic_records_only': True,
                       'batch_21_read_or_assessed': False,
                       'null_empty_omitted_diagnostics_equivalent': True,
                       'null_assessment': null_assessment, 'summary': summary})
    print({'status': 'passed', 'synthetic_assessed': 2, 'matched': 1,
           'match_rate': 0.5, 'solver_calls': 0, 'batch_21_assessed': False})


if __name__ == '__main__':
    main()
