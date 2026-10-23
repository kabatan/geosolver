"""Summarize numerical checks already saved before the optional float export.

The original audit, its output, its thresholds and the solver scorer stay intact.
No substitution, refinement, optimization or solver trial is repeated here.
"""
from __future__ import annotations

from decimal import Decimal

from common import BASE, EXTERNAL, read, save, sha


def main():
    audit = read(BASE / 'geometry-audit.json')
    path = EXTERNAL / 'original-substitutions.json'
    assert sha(path.read_bytes()) == audit['external_rows_sha256']
    rows = read(path)
    assert len(rows) == audit['representatives']
    threshold = Decimal(audit['normalized_residual_threshold'])
    assert threshold == Decimal('1e-20')
    checked, incomplete, numerical_failures, export_errors = [], [], [], []
    for row in rows:
        required = ('normalized_original_residual', 'original_hard_feasible',
                    'answer_relative_error', 'original_answer')
        if not all(key in row for key in required):
            incomplete.append(row['key'])
            continue
        residual = Decimal(row['normalized_original_residual'])
        answer_error = Decimal(row['answer_relative_error'])
        passed = (residual.is_finite() and answer_error.is_finite()
                  and residual <= threshold and answer_error <= threshold
                  and row['original_hard_feasible'] is True)
        checked.append((residual, answer_error, passed))
        if not passed:
            numerical_failures.append(row)
        if row.get('error'):
            assert row['error'].startswith('HighPrecisionContaminationError: float(mpf) in HP mode:')
            export_errors.append(row['key'])
    # The saved 20-significant-digit values are far from the unchanged cutoff;
    # rounding at serialization cannot account for an apparent pass here.
    assert all(abs(v - threshold) > threshold / 100 for r, a, _ in checked for v in (r, a))
    save(BASE / 'geometry-checks.json', {
        'scope': 'numerical fields recorded before optional float export; not a new audit or exact proof',
        'representatives': len(rows), 'complete_numerical_records': len(checked),
        'numerical_pass': sum(passed for _, _, passed in checked),
        'numerical_failures': numerical_failures, 'incomplete_records': incomplete,
        'precision_dps': audit['precision_dps'], 'threshold': str(threshold),
        'max_normalized_original_residual': str(max(r for r, _, _ in checked)),
        'max_answer_relative_error': str(max(a for _, a, _ in checked)),
        'original_audit_pass_flag': audit['pass'],
        'optional_float_export_errors': len(export_errors),
        'original_rows_sha256': sha(path.read_bytes()),
        'original_audit_sha256': sha((BASE / 'geometry-audit.json').read_bytes()),
        'original_script_sha256': sha((BASE / 'audit_geometry.py').read_bytes()),
        'explanation': 'audit_geometry.py records the numerical checks, then calls float(mpf) inside high_precision_mode while exporting points. The exception handler overwrites pass=False. Original flags/errors are retained; this summary separately counts the recorded numerical checks.'})
    print('Numerical checks:', sum(p for _, _, p in checked), '/', len(rows),
          '; optional float export errors:', len(export_errors))


if __name__ == '__main__':
    main()
