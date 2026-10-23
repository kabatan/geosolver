"""Reassess batches 0..20 in copies; never assess batch 21 or run a solver."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from support import (CLEAN, EXTERNAL, canonical, check_guard, check_patch,
                     destination, install_no_solver_guard, inventory, load_grader,
                     now, plan, require, save)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Use a new evidence directory; never overwrite evidence')
    guard = install_no_solver_guard()
    patch = check_patch()
    batches = plan()['batches']
    pending = destination(batches[21])
    require(not (pending / 'assessment.jsonl').exists(), 'Batch 21 must remain unassessed')
    require(len(list((pending / 'runs').glob('*/*.json'))) == 4, 'Four pending raw runs required')
    before = inventory(EXTERNAL)
    grader = load_grader()
    import geosolver
    from geosolver.runtime.integrity import source_tree_hash
    from support import SOURCE_HASH
    require(Path(geosolver.__file__).resolve().parent == CLEAN / 'src/geosolver', 'Wrong import')
    require(source_tree_hash() == SOURCE_HASH, 'Wrong frozen source')
    rows, batch_reports = [], []
    args.output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='q38-stage1-rescore-') as temp:
        for batch in batches[:21]:
            original = destination(batch)
            require((original / 'assessment.jsonl').is_file(), 'Completed assessment missing')
            copied = Path(temp) / original.name
            shutil.copytree(original, copied)
            grader.assess_campaign(copied, cases_path=CLEAN / batch['cases'])
            old_bytes = (original / 'assessment.jsonl').read_bytes()
            new_bytes = (copied / 'assessment.jsonl').read_bytes()
            old = [json.loads(line) for line in old_bytes.splitlines()]
            new = [json.loads(line) for line in new_bytes.splitlines()]
            expected_keys = {(identifier, batch['seed']) for identifier in batch['case_ids']}
            require({(r['case_id'], r['seed']) for r in old} == expected_keys,
                    'Unexpected completed assessment keys')
            require(len(old) == len(new) == 4, 'Expected exactly four assessments')
            for previous, current in zip(old, new, strict=True):
                rows.append({'batch': batch['batch'], 'mode': batch['mode'],
                             'case_id': previous['case_id'], 'seed': previous['seed'],
                             'all_fields_equal': previous == current,
                             'old_matched': previous['matched'], 'new_matched': current['matched'],
                             'old_row_sha256': hashlib.sha256(canonical(previous)).hexdigest(),
                             'new_row_sha256': hashlib.sha256(canonical(current)).hexdigest()})
            target = args.output / 'assessments' / f"{batch['batch']:03d}.assessment.jsonl"
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(new_bytes)
            batch_reports.append({'batch': batch['batch'], 'rows': len(new),
                                  'byte_identical': old_bytes == new_bytes,
                                  'old_assessment_path': str(original / 'assessment.jsonl'),
                                  'old_sha256': hashlib.sha256(old_bytes).hexdigest(),
                                  'new_sha256': hashlib.sha256(new_bytes).hexdigest()})
    after = inventory(EXTERNAL)
    require(before == after, 'Historical campaign/receipt files were modified')
    require(not (pending / 'assessment.jsonl').exists(), 'Batch 21 was assessed')
    check_guard(guard)
    require(len(rows) == 84, 'Expected exactly 84 comparisons')
    equal = sum(row['all_fields_equal'] for row in rows)
    report = {'checked_at_utc': now(), 'solver_calls': 0, 'guard': guard,
              'grader_patch': patch, 'source_hash': source_tree_hash(),
              'import_file': geosolver.__file__, 'batches': batch_reports,
              'assessments_compared': len(rows), 'all_fields_equal_count': equal,
              'mismatch_count': len(rows) - equal,
              'all_21_assessment_files_byte_identical': all(r['byte_identical'] for r in batch_reports),
              'historical_files_unchanged': before == after, 'historical_file_count': len(before),
              'batch_21_assessed': False, 'batch_21_raw_count': 4,
              'new_solver_runs': 0, 'new_execution_receipts': 0}
    save(args.output / 'preserved-inputs.json', {'root': str(EXTERNAL), 'files': before})
    save(args.output / 'result.json', report)
    with (args.output / 'comparison-84.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    require(equal == 84 and report['all_21_assessment_files_byte_identical'],
            'Assessment regression: inspect result.json')
    print({'assessments_identical': equal, 'mismatches': len(rows) - equal, 'solver_calls': 0,
           'historical_files_unchanged': True, 'batch_21_assessed': False})


if __name__ == '__main__':
    main()
