"""Reuse the old selection; stage an independently checked frozen runtime."""
import datetime as dt
import os
import shutil
import subprocess

from common import *


def main():
    destination = ROOT / 'jssa/difficulty/sweep/c-swap-target'
    assert BASE != destination and not destination.exists()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == FROZEN
    assert not subprocess.check_output(['git', 'diff', 'HEAD', '--'], cwd=ROOT)
    selection = read(BASE / 'selection.json')
    jobs = read(BASE / 'schedule.json')
    assert len(selection['cases']) == 20 and len(jobs) == 200
    for case in selection['cases']:
        original = read(BASE / case['variants']['original']['path'])
        for kind, variant in case['variants'].items():
            value = read(BASE / variant['path'])
            assert digest(value) == variant['dsl_sha256']
            assert {k:v for k,v in value.items() if k != 'target'} == {k:v for k,v in original.items() if k != 'target'}
        assert case['selection_rank'] == rank(case['pool'], case['id'])
    old_raw = Path('/tmp/q43c-swap-target-20261024')
    previous = []
    for folder in sorted((old_raw / 'runs').glob('*')):
        receipt = folder / 'receipt.json'
        record = read(receipt) if receipt.exists() else {}
        previous.append({'index': int(folder.name), 'receipt_present': receipt.exists(),
                         'status': record.get('result', {}).get('status', 'interrupted'),
                         'sha256': sha(receipt) if receipt.exists() else None,
                         'source_import': record.get('source', {}).get('import_file')})
    shutil.copytree(BASE, destination, ignore=shutil.ignore_patterns('__pycache__'))
    probe = 'from common import verify_source;import json;print(json.dumps(verify_source()))'
    source = json.loads(subprocess.check_output([str(PYTHON), '-B', '-c', probe], cwd=destination, env=environment(), text=True))
    manifest = {
        'created_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'frozen_commit': FROZEN, 'source': source, 'runtime_root': str(ROOT),
        'selection_sha256': sha(BASE / 'selection.json'), 'schedule_sha256': sha(BASE / 'schedule.json'),
        'selection_preserved': True, 'target_only_variants_checked': 100,
        'parallelism': 2, 'cores_per_run': 1, 'cpus': selection['cpus'][-2:],
        'time_limit_seconds': 180, 'planned_runs': 200, 'loadavg_start': os.getloadavg(),
        'raw_directory': str(RAW), 'old_raw_directory_preserved': str(old_raw),
        'previous_attempts': previous,
        'previous_attempts_policy': 'Retain every prior attempt in audit. Clean campaign runs all 200 fixed jobs, not selected failures. Prior shared-worktree result is not pooled with isolated runs.',
        'runtime_override': 'Historical selection.json records 3 lanes and shared import. This manifest supersedes execution settings only; selection, seeds, inputs and schedule are unchanged.',
        'code_sha256': {p.name: sha(p) for p in BASE.glob('*.py')},
    }
    save(BASE / 'resume-manifest.json', manifest)
    save(destination / 'resume-manifest.json', manifest)
    RAW.mkdir(parents=True, exist_ok=True)
    save(RAW / 'resume-manifest.json', manifest)
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    main()
