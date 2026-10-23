"""Check saved artifacts and reported arithmetic, without solving or regrading."""
from pathlib import Path
import csv
import datetime as dt
import hashlib
import json
import math

import report_repaired as report
import stage2

BASE = Path(__file__).resolve().parent
ROOT = stage2.EXTERNAL


def csv_rows(name):
    with (BASE / name).open(newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    checks = {}
    checks['locked_files'] = {str(p): stage2.check_lock(p) for p in (BASE, stage2.INPUT)}
    assert stage2.git('rev-parse', 'HEAD') == stage2.COMMIT
    assert not stage2.git('status', '--porcelain')
    assert not stage2.git('diff', stage2.FROZEN, '--', 'src', 'benchmarks/research_runner.py',
                         'benchmarks/cases.jsonl', 'pyproject.toml', 'uv.lock')
    checks['authorized_checkout_clean_and_frozen_products_unchanged'] = True
    archive = BASE / 'execution-records/invalid-attempt-20261023T164136Z'
    archived = stage2.read(archive / 'archive-manifest.json')
    for r in archived['archived_files']:
        p = BASE / r['archive_path']
        assert p.stat().st_size == r['bytes'] and stage2.sha(p) == r['sha256']
    for r in archived['raw_files_preserved_in_place']:
        p = Path(r['path'])
        assert p.stat().st_size == r['bytes'] and stage2.sha(p) == r['sha256']
    checks['old_invalid_attempt_byte_preserved'] = True
    old_script = (archive / 'stage2.py').read_text()
    assert (BASE / 'stage2.py').read_text() == old_script.replace(
        "EXTERNAL = Path('/tmp/q38-58e3993-execution')", "EXTERNAL = Path('/tmp/q38-58e3993-repaired-execution')"
    ).replace("PYTHON = Path('/home/kabatan/work/solver/.venv/bin/python')", "PYTHON = Path('/tmp/q38-58e3993-venv/bin/python')")
    checks['stage2_only_two_environment_path_bindings_changed'] = True
    assert Path('/home/kabatan/work/solver/.venv/lib/python3.12/site-packages/_editable_impl_geosolver.pth').read_text() == '/home/kabatan/work/solver/src'
    assert Path('/tmp/q38-58e3993-venv/lib/python3.12/site-packages/_editable_impl_geosolver.pth').read_text().strip() == '/tmp/q38-58e3993-clean/src'
    checks['original_and_repaired_pth_unchanged_since_repair'] = True
    plan = stage2.read(BASE / 'execution-plan.json')
    receipts = [stage2.read(p) for p in sorted((ROOT / 'receipts').glob('*.json'))]
    assert [r['batch'] for r in receipts] == list(range(22))
    assert all(r['state'] == 'complete' for r in receipts[:-1]) and receipts[-1]['state'] == 'stopped'
    for previous, following in zip(receipts, receipts[1:]):
        assert dt.datetime.fromisoformat(previous['finished_at_utc']) <= dt.datetime.fromisoformat(following['started_at_utc'])
    expected_raw, assessed, import_observed = {}, {}, 0
    for r in receipts:
        batch, dest, _ = stage2.paths(r['batch'])
        expected_argv = [x.replace('<verified-python3.12>', str(stage2.PYTHON)).replace(
            '<external-results-root>', str(ROOT / 'campaigns')) for x in batch['run_argv_after_separate_authorization']]
        assert r['commands'][0]['argv'] == expected_argv
        assert r['case_ids'] == batch['case_ids'] and r['seed'] == batch['seed'] and r['mode'] == batch['mode']
        cpus = []
        for identifier in batch['case_ids']:
            path = dest / 'runs' / identifier / f"{batch['seed']}.json"
            raw = stage2.read(path)
            key = (identifier, batch['mode'], batch['seed'])
            assert key not in expected_raw
            expected_raw[key] = raw
            assert not raw['execution_contract_issues']
            assert raw['source_hash'] == 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
            assert raw['config']['time_limit_seconds'] == 180 and raw['config']['cores'] == 1
            assert set(raw['config']['thread_environment'].values()) == {'1'}
            process = raw['process']
            cpus.append(process['assigned_cpu'])
            assert process['actual_affinity'] == [process['assigned_cpu']]
            info = ((raw.get('solver_result') or {}).get('diagnostics') or {}).get('process_info')
            if info:
                assert info['import_root'] == str(stage2.CLEAN / 'src/geosolver')
                assert info['cpu_affinity'] == [process['assigned_cpu']]
                import_observed += 1
        assert sorted(cpus) == [0, 1, 2, 3]
        for line in (dest / 'SHA256SUMS').read_text().splitlines():
            digest, filename = line.split('  ', 1)
            assert stage2.sha(dest / filename) == digest
        p = dest / 'assessment.jsonl'
        if p.exists():
            for line in p.read_text().splitlines():
                a = json.loads(line)
                assessed[a['case_id'], batch['mode'], a['seed']] = a
    assert len(expected_raw) == 88 and len(assessed) == 84 and import_observed == 87
    checks['fixed_prefix_22_batches_no_overlap_or_skips'] = True
    checks['exact_plan_argv_budget_threads_cpu_affinity_and_checksums'] = True
    checks['worker_import_root_verified_runs'] = import_observed
    checks['worker_import_root_unobservable_engine_error_runs'] = 1
    runs = csv_rows('runs.csv')
    assert len(runs) == 840 and len({(r['id'], r['mode'], int(r['seed'])) for r in runs}) == 840
    for r in runs:
        key = r['id'], r['mode'], int(r['seed'])
        a = assessed.get(key)
        assert r['matched'] == (str(a['matched']) if a else '')
        if a:
            assert float(r['wall_seconds']) == a['wall_seconds']
            assert float(r['capped_cost']) == (min(a['wall_seconds'], 180) if a['matched'] else 180)
        else:
            assert r['wall_seconds'] == r['capped_cost'] == ''
    assert sum(r['state'] == 'not_started' for r in runs) == 752
    checks['all_840_cells_and_exact_assessment_copy_no_custom_grading'] = True
    pairs = csv_rows('pairs.csv')
    assert len(pairs) == 720
    for p in pairs:
        orig = assessed.get((p['id'], 'original', int(p['seed'])))
        variant = assessed.get((p['id'], p['mode'], int(p['seed'])))
        if orig and variant:
            x, y = orig['wall_seconds'], variant['wall_seconds']
            direction = 'slower' if y >= 3 * x and y - x >= 2 else 'faster' if x >= 3 * y and x - y >= 2 else 'below_threshold'
            assert p['large_timing_direction'] == direction
            assert math.isclose(float(p['variant_over_original']), y / x, rel_tol=1e-14)
        else:
            assert not p['large_timing_direction'] and not p['variant_over_original']
    comparisons = csv_rows('per-comparison.csv')
    assert len(comparisons) == 240
    for c in comparisons:
        pp = [p for p in pairs if (p['id'], p['mode']) == (c['id'], c['mode'])]
        assert len(pp) == 3
        if c['all_three_pairs_assessed'] == 'True':
            assert c['A'] == 'False' and c['T'] == 'False'
            assert sum(p['large_timing_direction'] in ('faster', 'slower') for p in pp) <= 1
        else:
            assert c['A'] == c['T'] == ''
    checks['paired_ratios_thresholds_and_missing_values_independently_checked'] = True
    assert len(csv_rows('per-problem.csv')) == 40 and len(csv_rows('per-stratum.csv')) == 8
    summary = stage2.read(BASE / 'results-summary.json')
    assert summary['A_count'] is None and summary['T_count'] is None and not summary['predictions_tested']
    assert summary['graded_correct'] == 84 and summary['graded_incorrect'] == 0
    assert summary['completed_subset_only']['problems'] == 4
    checks['partial_four_problem_results_not_promoted_to_40_problem_predictions'] = True
    all_files = [p for root in (BASE, ROOT) for p in root.rglob('*') if p.is_file()]
    assert max(p.stat().st_size for p in all_files) < 5_000_000
    checks['max_file_bytes'] = max(p.stat().st_size for p in all_files)
    # Boundary cases exercise the preregistered criterion, without a solver.
    def fake(wall, matched=True):
        return {'id': 'synthetic', 'mode': 'condition_order', 'seed': 0, 'matched': matched,
                'state': 'assessed', 'wall_seconds': wall, 'capped_cost': min(wall, 180) if matched else 180}
    slow = report.pair(fake(1), fake(3))
    fast = report.pair(fake(3), fake(1))
    small = report.pair(fake(.2), fake(.6))
    failed = report.pair(fake(1), fake(20, False))
    assert slow['large_timing_direction'] == 'slower'
    assert fast['large_timing_direction'] == 'faster'
    assert small['large_timing_direction'] == 'below_threshold'
    assert failed['large_timing_direction'] is None
    assert report.comparison('synthetic', 'condition_order', [slow, slow, fast])['T'] is True
    assert report.comparison('synthetic', 'condition_order', [slow, fast, small])['T'] is False
    checks['timing_boundary_and_same_direction_criterion_checks'] = True
    stage2.save(BASE / 'verification.json', {'at_utc': stage2.now(), 'solver_calls': 0,
        'status': 'passed', 'scope': 'Integrity and reporting checks; does not complete the halted experiment.',
        'report_script_sha256': stage2.sha(BASE / 'report_repaired.py'), 'checks': checks})
    print(json.dumps({'status': 'passed', 'solver_calls': 0, 'checked_raw': 88, 'checked_assessments': 84,
                      'planned_cells': 840, 'max_bytes': checks['max_file_bytes']}))


if __name__ == '__main__':
    main()
