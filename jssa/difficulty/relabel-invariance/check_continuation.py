"""Recheck the sealed gate and the already completed prefix before continuation.

The sealed initial gate requires exactly 88 historical runs. It is executed
unchanged; its sole expected failure after authorized progress is recorded.
All remaining import checks are repeated through its unchanged --probe entry.
No historical file, solver, grader, seed, budget or execution adapter is edited.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'amendment-null-diagnostics'))
import support as s
import check_before_resume as gate
import resume_null_stage2 as adapter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    s.require(not args.output.exists(), 'Use a new continuation receipt')
    started = s.now()
    guard = s.install_no_solver_guard(allow_processes=True)
    initial_gate_failure = None
    saved_argv = sys.argv
    try:
        sys.argv = [str(Path(gate.__file__)), '--output', str(args.output)]
        gate.main()
    except RuntimeError as error:
        expected = 'This resumption gate expects exactly the original 88 raw runs'
        s.require(str(error) == expected, 'Initial gate failed for another reason: ' + str(error))
        initial_gate_failure = str(error)
    finally:
        sys.argv = saved_argv
    s.require(initial_gate_failure is not None, 'This continuation gate requires existing resumed progress')
    seal = adapter.common_checks()
    s.require(s.sha(Path(seal['preflight_path'])) == seal['preflight_sha256'], 'Initial preflight changed')
    batches = s.plan()['batches']
    historical_paths = set()
    for batch in batches[:22]:
        dest = s.destination(batch)
        paths = set(dest.glob('runs/*/*.json'))
        expected = {dest / 'runs' / i / f"{batch['seed']}.json" for i in batch['case_ids']}
        s.require(paths == expected, 'Historical batch cells changed')
        historical_paths.update(paths)
    s.require(len(historical_paths) == 88, 'Historical 88-run prefix changed')
    expected_steps = [(n, p) for n in range(22, 210) for p in (0, 1, 'final')]
    receipts = sorted((adapter.ROOT / 'receipts').glob('*.json'))
    records = [s.read(p) for p in receipts]
    observed = [(r['batch'], r.get('wave', 'final')) for r in records]
    s.require(observed == expected_steps[:len(observed)], 'Resumed steps are not the fixed prefix')
    s.require(all(r['state'] == 'complete' for r in records), 'An unfinished attempt requires explicit accounting')
    expected_campaigns = {s.destination(b) for b in batches[:22]}
    expected_waves = set()
    raw_count = 88
    assessed_count = 88  # Includes the separate, hash-verified batch-21 recovery.
    for path, record in zip(receipts, records):
        s.require(s.sha(path) == s.sha(adapter.LOCAL / path.name), 'Local/external receipt mismatch')
        dest = Path(record['destination'])
        adapter.verify_inventory(dest, record['outputs'])
        batch = batches[record['batch']]
        if 'wave' in record:
            ids = batch['case_ids'][:3] if record['wave'] == 0 else batch['case_ids'][3:]
            s.require(record['case_ids'] == ids, 'Changed wave case order')
            adapter.validate_wave(dest, batch, ids)
            expected_waves.add(dest)
            raw_count += len(ids)
        else:
            expected_campaigns.add(dest)
            assessed_count += 4
    for previous, current in zip(records, records[1:]):
        s.require(previous['finished_at_utc'] <= current['started_at_utc'], 'Prior steps overlapped')
    s.require(set((s.EXTERNAL / 'campaigns').iterdir()) == expected_campaigns, 'Unexpected campaign directory')
    s.require(set((adapter.ROOT / 'waves').iterdir()) == expected_waves, 'Unexpected wave directory')
    parent_argv = [str(s.PYTHON), '-B', str(Path(gate.__file__)), '--probe']
    env = os.environ | s.plan()['environment']
    parent = json.loads(subprocess.check_output(parent_argv, cwd=s.CLEAN, env=env, text=True, timeout=60))
    with tempfile.TemporaryDirectory(prefix='q38-continuation-import-probe-') as temporary:
        child = json.loads(subprocess.check_output(parent_argv, cwd=temporary, env=env, text=True, timeout=60))
    s.require(parent['runtime_fingerprint'] == child['runtime_fingerprint'], 'Parent/child imports differ')
    expected_deps = s.read(BASE / 'execution-records/environment-repair.json')['child_probe']['dependencies']
    for name, version in parent['runtime_fingerprint']['runtime_dependencies'].items():
        s.require(expected_deps.get(name) == version, 'Dependency changed: ' + name)
    s.require(not gate.git('status', '--porcelain', '--untracked-files=all'), 'Probe dirtied frozen checkout')
    s.check_guard(guard)
    next_step = expected_steps[len(observed)] if len(observed) < len(expected_steps) else None
    value = {
        'status': 'passed', 'started_at_utc': started, 'checked_at_utc': s.now(),
        'purpose': 'immediately_before_continuation_of_authorized_prefix',
        'user_authorization': 'Current user instructs Q38 continuation under commit 65627f72 and resume_common.txt.',
        'solver_calls': 0, 'grading_calls': 0, 'retries': 0, 'replacements': 0,
        'unchanged_initial_gate_path': str(Path(gate.__file__)),
        'unchanged_initial_gate_sha256': s.sha(Path(gate.__file__)),
        'initial_gate_failure': initial_gate_failure,
        'gate_resolution': 'Original 88 files checked separately; all additional trials verified against sealed adapter receipts and the exact fixed prefix. No initial check was disabled.',
        'implementation_sha256': s.sha(Path(__file__)),
        'supplement_lock': s.check_supplement_lock(), 'original_lock': s.check_original_lock(BASE),
        'grader_patch': s.check_patch(), 'adapter_seal_sha256': s.sha(adapter.ROOT / 'adapter-seal.json'),
        'historical_raw_count': 88, 'total_unique_executed_cells': raw_count,
        'assessed_cells': assessed_count, 'unassessed_saved_cells': raw_count - assessed_count,
        'completed_resumption_steps': len(records), 'next_step': next_step,
        'receipt_sha256': {p.name: s.sha(p) for p in receipts},
        'environment': s.plan()['environment'], 'parent_probe': parent,
        'temporary_cwd_child_probe': child, 'guard': guard,
        'loadavg': os.getloadavg(),
        'limitations': 'Import-only check; no actual worker launch. Completed attempts are retained without rerun.'
    }
    s.save(args.output, value)
    print(json.dumps({k: value[k] for k in ('status', 'solver_calls', 'total_unique_executed_cells',
                                          'assessed_cells', 'next_step')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
