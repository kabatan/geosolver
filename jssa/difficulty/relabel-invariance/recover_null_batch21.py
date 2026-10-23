"""Authorized batch-21 recovery; copied inputs and zero solver calls only."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'amendment-null-diagnostics'))
import support as s

ROOT = Path('/tmp/q38-null-diagnostics-authorized-resume')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', type=Path, required=True)
    args = parser.parse_args()
    guard = s.install_no_solver_guard()
    receipt_path = ROOT / 'recovery-021.json'
    s.require(not receipt_path.exists(), 'Recovery already attempted; do not retry')
    authorization = s.read(ROOT / 'authorization.json')
    preflight = s.read(args.preflight)
    s.require(authorization['authorization_commit'].startswith('65627f72'), 'Wrong authorization')
    s.require(preflight['status'] == 'passed' and preflight['solver_calls'] == 0
              and preflight['purpose'] == 'immediately_before_authorized_resume'
              and preflight['supplement_lock'], 'Fresh sealed preflight required')
    s.check_supplement_lock()
    batch = s.plan()['batches'][21]
    original = s.destination(batch)
    copied = ROOT / 'recovered-campaigns' / original.name
    before = s.inventory(s.EXTERNAL)
    record = {'batch': 21, 'state': 'starting', 'started_at_utc': s.now(),
              'authorization': authorization, 'preflight_path': str(args.preflight),
              'preflight_sha256': s.sha(args.preflight), 'solver_calls': 0,
              'original_campaign': str(original), 'recovered_campaign': str(copied),
              'implementation_sha256': s.sha(Path(__file__)),
              'original_stopped_receipt_sha256': s.sha(s.EXTERNAL / 'receipts/021.json')}
    s.save(receipt_path, record)
    try:
        s.require(not copied.exists(), 'Recovery output must be new')
        s.require(not (original / 'assessment.jsonl').exists(), 'Original must remain unassessed')
        for line in (original / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            s.require(s.sha(original / name) == digest, 'Original checksum mismatch: ' + name)
        inputs = s.inventory(original)
        shutil.copytree(original, copied)
        s.require(s.inventory(copied) == inputs, 'Copied input hashes differ')
        record['copied_inputs_sha256_verified'] = True
        record['inputs'] = inputs
        record['grader_patch'] = s.check_patch()
        grader = s.load_grader()
        import geosolver
        from geosolver.runtime.integrity import source_tree_hash
        s.require(Path(geosolver.__file__).resolve().parent == s.CLEAN / 'src/geosolver', 'Wrong import')
        s.require(source_tree_hash() == s.SOURCE_HASH, 'Wrong frozen source')
        record['import_file'] = geosolver.__file__
        record['source_hash'] = source_tree_hash()
        cases = s.CLEAN / batch['cases']
        record['cases_path'] = str(cases)
        record['cases_sha256'] = s.sha(cases)
        grader.assess_campaign(copied, cases_path=cases)
        record['assess_completed_at_utc'] = s.now()
        grader.summarize_campaign(copied)
        record['summarize_completed_at_utc'] = s.now()
        rows = [json.loads(line)
                for line in (copied / 'assessment.jsonl').read_text().splitlines()]
        s.require(len(rows) == 4 and {(r['case_id'], r['seed']) for r in rows}
                  == {(i, batch['seed']) for i in batch['case_ids']}, 'Recovery cell mismatch')
        for row in rows:
            raw = s.read(copied / 'runs' / row['case_id'] / f"{row['seed']}.json")
            s.require(not raw['execution_contract_issues'], 'Saved contract violation')
            if ((raw.get('solver_result') or {}).get('error') or {}).get('code') == 'artifact_missing':
                s.require(row['matched'] is False and row['normal_completion'] is False
                          and row['failure_stage'] == 'runtime', 'Missing worker incorrectly graded')
        for name, entry in inputs.items():
            if name != 'SHA256SUMS':
                s.require(s.sha(copied / name) == entry['sha256'], 'Copied raw input mutated')
        s.require(s.inventory(s.EXTERNAL) == before, 'Original historical files changed')
        s.check_guard(guard)
        record.update(state='complete', outputs=s.inventory(copied), guard=guard,
                      historical_files_unchanged=True, historical_file_count=len(before),
                      summary=s.read(copied / 'summary.json'))
    except BaseException as error:
        record.update(state='stopped', error=repr(error), traceback=traceback.format_exc(), guard=guard)
        raise
    finally:
        record['finished_at_utc'] = s.now()
        s.save(receipt_path, record)
        s.save(BASE / 'resume-records/recovery-021.json', record)
    print({'state': record['state'], 'solver_calls': 0, 'summary': record['summary']})


if __name__ == '__main__':
    main()
