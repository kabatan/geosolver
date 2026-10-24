"""Verify saved preparation receipts and raw bytes; never launch a solver."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def main():
    sources = json.loads((OUT / 'source-hashes.json').read_text())
    freeze = json.loads((OUT / 'pre-smoke-hashes.json').read_text())
    # design.md is the only pre-smoke artifact amended after examining receipts.
    for name, digest in freeze['files_sha256'].items():
        if name != 'design.md':
            assert sha(OUT / name) == digest, name
    roots = {key:Path(sources[key + '_source'])
             for key in ('base', 'patched', 'replay', 'frozen')}
    for key in ('base', 'patched', 'frozen'):
        assert inventory(roots[key]) == sources[key + '_files_sha256'], key
    assert inventory(roots['replay']) == sources['patched_files_sha256']
    for name, digest in sources['protected_files'].items():
        data = [(root / name).read_bytes() for root in roots.values()]
        assert all(blob == data[0] for blob in data), name
        assert hashlib.sha256(data[0]).hexdigest() == digest
    assert len(sources['protected_files']) == 12
    for name in sources['patched_files_sha256']:
        if name.endswith('.py'):
            ast.parse((roots['patched'] / name).read_text(), filename=name,
                      feature_version=(3, 12))
    assert sha(OUT / 'switch-b.patch') == sources['patch_sha256']
    repo = OUT.parents[5]
    assert sha(repo / sources['provenance']['path']) == sources['provenance']['sha256']
    for root, options in ((roots['base'], []), (roots['patched'], ['--reverse'])):
        subprocess.run(['git', 'apply', '--check', *options, str(OUT / 'switch-b.patch')],
                       cwd=root, check=True, timeout=10)
    inputs = json.loads((OUT / 'inputs.json').read_text())
    for row in inputs:
        assert sha(Path(row['path'])) == row['sha256']
    baseline = (OUT / 'smoke/probe.BASE1.json').read_bytes()
    rows = {p.name[6:-5]:json.loads(p.read_bytes())
            for p in (OUT / 'smoke').glob('probe.*.json') if p.name != 'probe.BASE1.json'}
    for arm in ('B0', 'ALL_ZERO'):
        assert (OUT / f'smoke/probe.{arm}.json').read_bytes() == baseline
    # Reuse the exact original contract assertions without running main/jobs.
    driver = (OUT / 'smoke_driver.py').read_text()
    begin = driver.index("    b=rows['B0']")
    end = driver.index('    jobs=[]', begin)
    assertions = '\n'.join(line[4:] for line in driver[begin:end].splitlines())
    exec(compile(assertions, str(OUT / 'smoke_driver.py') + ':saved-contracts', 'exec'),
         {'rows':rows})
    config = json.loads((OUT / 'configs.json').read_text())
    driver_receipt = json.loads((OUT / 'smoke/driver.json').read_text())
    jobs = driver_receipt['jobs']
    expected = {(arm, task['case_id']) for arm in config['smoke']['full_process_arms']
                for task in inputs}
    assert {(j['arm'], j['case_id']) for j in jobs} == expected
    assert len(jobs) == len(expected) == 14
    assert driver_receipt['max_parallel'] <= 2
    passed, crashed = [], []
    for job in jobs:
        assert not job['outer_timeout'] and job['wall_seconds'] < 10
        name = f"{job['arm']}.{job['case_id']}"
        receipt = OUT / 'smoke' / (name + '.json')
        if job['arm'] == 'B045':
            assert job['returncode'] == -11 and not receipt.exists()
            crashed.append(name)
            continue
        assert job['returncode'] == 0
        row = json.loads(receipt.read_text())
        assert row['process_state'] in ('returned', 'deadline')
        assert row['calls']['run_external_pipeline'] == 1
        assert row['lock_valid'] and row['source_hash'] == sources['patched_source_hash']
        assert row['active'] == [k.removeprefix('GEOSOLVER_ABLATE_')
                                 for k in config['arms'][job['arm']]]
        if job['arm'] in ('B006', 'B005_006'):
            assert row['calls'].get('dependencies', 0) == 0
        if job['arm'] == 'B046':
            assert row['nomad_penalties'].get('removed', 0) > 0
            assert row['nomad_penalties'].get('applied', 0) == 0
        passed.append(name)
    native = json.loads((OUT / 'native/checks.json').read_text())
    assert {j['case']:j['returncode'] for j in native['jobs']} == {
        'disco_hidden':0, 'disco_plain':-11, 'mads_plain':0, 'disco_revealing':0}
    assert all(not j['outer_timeout'] and j['wall_seconds'] < 10 for j in native['jobs'])
    assert native['max_parallel'] <= 2 and not native['network_used']
    for name, digest in native['sha256'].items():
        assert sha(Path(name)) == digest
    result = dict(contract_assertions_passed=True, contract_probe_arms=len(rows),
        default_probe_byte_identical=True, default_zero_flags_byte_identical=True,
        all_source_inventories_match=True, protected_raw_byte_identical_files=12,
        replay_byte_identical=True, patch_forward_reverse_check=True,
        full_process_jobs=14, full_process_passed=passed, full_process_sigsegv=crashed,
        all_full_process_jobs_passed=False, B045_native_operation='unconfirmed',
        B045_native_crash_reproduced=True, max_parallel=1, outer_seconds=10,
        quality_compared=False, measurement_run=False, full_pipeline_retries=0,
        presmoke_hash_changes={'design.md':dict(before=freeze['files_sha256']['design.md'],
                                               after=sha(OUT / 'design.md'))})
    (OUT / 'smoke/checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
