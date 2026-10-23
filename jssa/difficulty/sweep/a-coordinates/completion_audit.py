"""Verify existing Q43a artifacts without rerunning any solver trial."""
from __future__ import annotations

import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
import subprocess
from pathlib import Path

import coordinates as C


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(j):
    return f"{j['id']}__{j['variant']}__{j['seed']}__{j['budget']}"


def main():
    base, external = C.BASE, C.EXTERNAL
    manifest = load(base/'manifest.json')
    inputs = load(base/'inputs.json')
    assert all(C.digest(i['dsl']) == i['dsl_sha256'] for i in inputs)
    assert all(sha(base/n) == h for n, h in manifest['scripts'].items())
    resume = load(base/'resume-audit.json')
    followup_hash = next(r['original_sha256'] for r in resume['script_copies'] if r['name'] == 'followup.py')
    assert sha(base/'followup.py') == followup_hash
    clean = Path(resume['clean_checkout'])
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=clean, text=True).strip() == C.FROZEN
    assert not subprocess.check_output(['git', 'diff', C.FROZEN, '--', 'src'], cwd=clean)
    with (base/'selection-universe.csv').open() as f:
        universe = list(csv.DictReader(f))
    for group in ('development', 'unseen2026'):
        eligible = sorted([r for r in universe if r['group'] == group and r['eligible'] == 'True'], key=lambda r: r['rank'])
        chosen = [i['id'] for i in inputs if i['group'] == group]
        assert chosen == [r['id'] for r in eligible[:12]]
    long_selection = load(base/'long-selection.json')
    assert long_selection['source_summary_sha256'] == sha(base/'short-summary.json')
    result = dict(verified_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                  frozen_commit=C.FROZEN, expected_source_hash=C.EXPECTED,
                  solver_and_selection_scripts_unchanged=True,
                  clean_src_diff_empty=True, selection_reproduced=True,
                  short_original_driver_adopted=True, interrupted_trials=0,
                  additional_trials_or_retries=0, stages={})
    all_hashes, all_imports = collections.Counter(), collections.Counter()
    expected_stage_sizes = {'short': 1056, 'long': 240, 'fixedbox': 240}
    for stage, n in expected_stage_sizes.items():
        jobs = load(base/f'{stage}-jobs.json')
        complete = load(base/f'{stage}-complete.json')
        execution = load(base/f'{stage}-execution.json')
        assert len(jobs) == complete['jobs'] == n
        assert len(set(map(key, jobs))) == n
        assert {p.stem for p in (base/stage/'records').glob('*.json')} == set(map(key, jobs))
        assert {p.stem for p in (external/stage/'receipts').glob('*.json')} == set(map(key, jobs))
        assert execution['parallelism'] == 3
        rows, raw_bytes, imports = [], 0, collections.Counter()
        for order, j in enumerate(jobs):
            assert j['order'] == order
            r = load(base/stage/'records'/f'{key(j)}.json')
            assert all(r[k] == v for k, v in j.items())
            receipt = load(external/stage/'receipts'/f'{key(j)}.json')
            assert receipt['job'] == j
            assert receipt['returncode'] == 0 and not receipt['external_timeout']
            raw = Path(r['raw_path'])
            assert sha(raw) == r['raw_sha256']
            raw_bytes += raw.stat().st_size
            with gzip.open(raw, 'rt') as f:
                artifact = json.load(f)
            assert artifact['q43a_job'] == j
            assert r['source_hash'] == artifact['q43a_source']['source_hash'] == C.EXPECTED
            assert artifact['q43a_source']['engine_lock'] == [True, C.EXPECTED]
            inp = next(i for i in inputs if i['id'] == j['id'])
            variant = next(v for v in C.variants() if v['name'] == j['variant'])
            assert artifact['q43a_dsl_sha256'] == C.digest(C.transform(inp['dsl'], variant))
            assert r['exact_correct'] == (r['actual_keys'] == inp['reference_keys'])
            if stage == 'fixedbox':
                assert r['box_hook_applied'] > 0
                hook = artifact['diagnostics']['q43a_fixedbox']
                assert all(c['returned'] == hook['original_box'] for c in hook['calls'] if c['applied'])
            if stage != 'short':
                assert artifact['q43a_source']['import_file'] == str(clean/'src/geosolver/__init__.py')
            imports[artifact['q43a_source']['import_file']] += 1
            all_hashes[r['source_hash']] += 1
            rows.append(r)
        figures = load(base/f'{stage}-figures-summary.json')
        assert len(figures['rows']) == n
        assert all(not r['errors'] for r in figures['rows'])
        assert all(r['original_valid_witnesses'] == r['distinct_coordinates'] for r in figures['rows'])
        summary = load(base/f'{stage}-summary.json')
        assert summary['jobs'] == n and summary['correct'] == sum(r['exact_correct'] for r in rows)
        start, end = dt.datetime.fromisoformat(execution['started']), dt.datetime.fromisoformat(complete['finished'])
        result['stages'][stage] = dict(jobs=n, receipts=n, raw_hashes_checked=n,
            source_hashes_checked=n, exact_scores_checked=n, source_imports=dict(imports),
            statuses=dict(collections.Counter(r['status'] for r in rows)),
            correct=sum(r['exact_correct'] for r in rows), external_timeouts=0, worker_errors=0,
            started=execution['started'], finished=complete['finished'], wall_seconds=(end-start).total_seconds(),
            starting_load=execution['load'], raw_compressed_bytes=raw_bytes,
            valid_coordinate_records=sum(r['original_valid_witnesses'] for r in figures['rows']))
        all_imports.update(imports)
    result['total_trials'] = sum(expected_stage_sizes.values())
    result['source_hashes'] = dict(all_hashes)
    result['source_imports'] = dict(all_imports)
    samples_path = external/'resume-progress.jsonl'
    samples = [json.loads(line) for line in samples_path.read_text().splitlines()]
    result['load_samples'] = dict(path=str(samples_path), samples=len(samples),
                                 cpu_count=os.cpu_count(),
                                 minimum_1min=min(s['load'][0] for s in samples),
                                 maximum_1min=max(s['load'][0] for s in samples),
                                 caution='Shared-machine wall time; worker completion time is not time to first correct answer.')
    too_large = [str(p.relative_to(base)) for p in base.rglob('*') if p.is_file() and p.stat().st_size > 5_000_000]
    assert not too_large, too_large
    result['repository_files_over_5mb'] = too_large
    result['largest_repository_file_bytes'] = max(p.stat().st_size for p in base.rglob('*') if p.is_file())
    result['artifact_sha256'] = {p.name: sha(p) for p in sorted(base.glob('*')) if p.is_file() and p.name != 'completion-audit.json'}
    (base/'completion-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['total_trials', 'source_hashes', 'repository_files_over_5mb']}))


if __name__ == '__main__':
    main()
