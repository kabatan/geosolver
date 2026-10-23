"""Verify persisted evidence and frozen scoring without running the solver."""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

from common import BASE, EXTERNAL, FROZEN, SOURCE, fingerprint, read, save, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin', type=Path, required=True)
    args = parser.parse_args()
    origin = args.origin / 'jssa/difficulty/sweep/b-equivalent-forms'
    environment = read(origin / 'resume-environment.json')
    preserved = ('run.py', 'analyze.py', 'followup.py', 'common.py', 'transforms.py',
                 'audit_geometry.py', 'reference-keys.json', 'protocol.md', 'equivalence.md')
    for name in preserved:
        expected = environment['copied_files'][name]
        assert sha((BASE / name).read_bytes()) == expected, name
        assert sha((origin / name).read_bytes()) == expected, name
    manifest = read(BASE / 'input-manifest.json')
    assert sha((BASE / 'selection.json').read_bytes()) == manifest['selection_sha256']
    assert sha((BASE / 'jobs.json').read_bytes()) == manifest['jobs_sha256']
    for path, digest in manifest['files'].items():
        assert sha((BASE / path).read_bytes()) == digest, path
    design = read(BASE / 'followup-design.json')
    assert sha((BASE / 'summary.json').read_bytes()) == design['main_summary_sha256']
    assert sha((BASE / 'followup-selection-effects.json').read_bytes()) == design['main_effects_sha256']
    assert read(BASE / 'followup-jobs.json')['design_hash'] == sha(design)
    frozen_scorer = subprocess.check_output(
        ['git', 'show', f'{FROZEN}:benchmarks/research_runner.py'], cwd=args.origin)
    assert sha(frozen_scorer) == read(BASE / 'reference-keys.json')['frozen_runner_sha256']
    all_keys, records, incomplete_identities = set(), [], []
    for stem, cache_name in [('jobs', 'analysis-cache.json'),
                             ('followup-jobs', 'followup-cache.json')]:
        jobs = read(BASE / f'{stem}.json')['jobs']
        complete = read(BASE / f'completed-{stem}.json')
        launch = read(BASE / f'execution-{stem}.json')
        assert complete['completed'] == len(jobs)
        assert launch['jobs_hash'] == complete['jobs_hash'] == sha(jobs)
        assert launch['max_parallel'] == complete['max_parallel'] == 3
        assert launch['runtime']['source_hash'] == complete['final_runtime']['source_hash'] == SOURCE
        cache = read(EXTERNAL / cache_name)
        for job in jobs:
            assert job['key'] not in all_keys
            all_keys.add(job['key'])
            path = EXTERNAL / 'runs' / f'{job["key"]}.json'
            payload = path.read_bytes()
            raw = json.loads(payload)
            assert raw['job'] == job
            assert raw['runtime']['source_hash'] == SOURCE
            if 'input_hash' in raw:
                assert raw['input_hash'] == job['input_hash']
            assert sha(read(BASE / job['input'])) == job['input_hash']
            row = cache[job['key']]
            assert row['raw_sha256'] == sha(payload)
            if 'worker_cpu' in raw:
                assert raw['worker_cpu'] in launch['cpus']
            result = raw['solver_result']
            if result.get('engine'):
                assert result['engine']['source_hash'] == SOURCE
            else:
                assert result['status'] not in ('solved', 'no_answer_found')
                incomplete_identities.append(job['key'])
            if raw['runtime'].get('import'):
                assert Path(raw['runtime']['import']).parent == Path(launch['runtime']['import']).parent
            records.append({'key': job['key'], 'raw_sha256': sha(payload),
                            'raw_bytes': len(payload), 'source_hash': raw['runtime']['source_hash'],
                            'status': result['status'], 'matched': row['matched']})
    assert {p.stem for p in (EXTERNAL / 'runs').glob('*.json')} == all_keys
    assert {p.stem for p in (EXTERNAL / 'logs').glob('*.log')} == all_keys
    assert not list((EXTERNAL / 'runs').glob('*.tmp'))
    evidence_hash = hashlib.sha256()
    for record in sorted(records, key=lambda r: r['key']):
        evidence_hash.update(f'{record["key"]}\0{record["raw_sha256"]}\n'.encode())
    geometry = read(BASE / 'geometry-audit.json')
    numerical_geometry = read(BASE / 'geometry-checks.json')
    assert numerical_geometry['original_audit_sha256'] == sha((BASE / 'geometry-audit.json').read_bytes())
    assert numerical_geometry['original_rows_sha256'] == geometry['external_rows_sha256']
    large = [{'path': str(p.relative_to(BASE)), 'bytes': p.stat().st_size}
             for p in BASE.rglob('*') if p.is_file() and p.stat().st_size > 5_000_000]
    assert not large, large
    save(BASE / 'completion-audit.json', {
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'runtime': fingerprint(),
        'frozen_commit': FROZEN, 'preserved_files_sha256': {
            name: environment['copied_files'][name] for name in preserved},
        'input_files_verified': len(manifest['files']), 'planned_runs': len(all_keys),
        'recorded_runs': len(records), 'retries': 0, 'interrupted_runs': 0,
        'statuses': dict(collections.Counter(r['status'] for r in records)),
        'missing_worker_identity_on_failure': incomplete_identities,
        'raw_bytes': sum(r['raw_bytes'] for r in records),
        'key_and_raw_sha256_digest': evidence_hash.hexdigest(),
        'geometry_representatives': geometry['representatives'],
        'original_geometry_audit_pass_flag': geometry['pass'],
        'geometry_numerical_pass': numerical_geometry['numerical_pass'],
        'optional_geometry_float_export_errors': numerical_geometry['optional_float_export_errors'],
        'current_load': os.getloadavg(),
        'original_driver_adopted': True, 'new_solver_root': str(BASE.parents[3]),
        'repository_files_over_5mb': large,
        'note': 'Every planned key has one raw artifact and one log. Counts are not inferred from progress files.'})
    print('Verified', len(records), 'recorded runs and', len(manifest['files']), 'input hashes')


if __name__ == '__main__':
    main()
