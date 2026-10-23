"""Record authorization and verify committed inputs before any local search."""
from common import *
import importlib.metadata
import platform
import shutil
import subprocess


def main():
    repository = HERE.parents[4]
    base = HERE.parent
    assert not (HERE / 'receipt.json').exists(), 'Do not overwrite the authorization receipt'
    lock = read(base / 'prediction.lock.json')
    assert (base / 'prediction.lock.json').read_bytes() == subprocess.check_output(
        ['git', 'show', f'{COMMIT}:jssa/difficulty/perturb-given/a/prediction.lock.json'], cwd=repository)
    assert not PLAN.exists(), 'Do not replace the input snapshot'
    PLAN.mkdir(parents=True)
    for name, record in lock['files'].items():
        data = (base / name).read_bytes()
        assert sha(data) == record['sha256'] and len(data) == record['bytes'], name
        committed = subprocess.check_output(
            ['git', 'show', f'{COMMIT}:jssa/difficulty/perturb-given/a/{name}'], cwd=repository)
        assert data == committed, name
        dest = PLAN / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    shutil.copyfile(base / 'prediction.lock.json', PLAN / 'prediction.lock.json')
    sibling = base.parent / 'b/shared'
    shared = {}
    for path in sorted(sibling.rglob('*')):
        if path.is_file():
            name = str(path.relative_to(sibling))
            assert path.read_bytes() == (PLAN / name).read_bytes(), name
            shared[name] = sha(path.read_bytes())
    source = verify_source()
    from geosolver.runtime.integrity import installed_dependencies, verify_engine_lock
    assert verify_engine_lock()[0]
    selected = read(PLAN / 'selected.json')
    plan_digest = hashlib.sha256()
    count = 0
    for case in selected:
        for seed, k, variant, position in schedule(case['canonical_id']):
            plan_digest.update(f"{case['canonical_id']}|{seed}|{k}|{variant}|{position}\n".encode())
            count += 1
    assert count == 144000
    receipt = {
        'task': 'Q40a', 'stage': 2, 'recorded_at_utc': utc(), 'execution_authorized': True,
        'authorization': {'source': 'user instruction in this stage-2 task',
            'prediction_and_common_contract_commit': COMMIT,
            'commit_push_confirmed_utc': '2026-10-23T18:02:20Z',
            'confirmed_by': 'Claude, as explicitly confirmed by the user',
            'git_commit_timestamp_utc': subprocess.check_output(
                ['git', 'show', '-s', '--format=%cI', COMMIT], cwd=repository, text=True).strip(),
            'remote_tracking_contains_commit': subprocess.check_output(
                ['git', 'branch', '-r', '--contains', COMMIT], cwd=repository, text=True).strip(),
            'note': 'Push confirmation is the user-provided evidence; no fresh network query.'},
        'prediction_lock_sha256': sha((PLAN / 'prediction.lock.json').read_bytes()),
        'locked_files_verified': len(lock['files']), 'shared_files_verified': len(shared),
        'frozen_commit': FROZEN, 'checkout': str(CLEAN), 'checkout_clean': True,
        'source_files_verified': 251, 'source_hash': source,
        'external_raw_directory': str(EXTERNAL), 'planned_trials': count,
        'schedule_sha256': plan_digest.hexdigest(),
        'parallel_workers': 2, 'threads_per_worker': 1, 'command_limit_seconds': 200,
        'local_deadline_seconds': 2, 'outer_local_limit_seconds': 5, 'build_limit_seconds': 60,
        'python': sys.version, 'executable': sys.executable, 'python_no_site': True,
        'sys_path': sys.path, 'dependencies': installed_dependencies(),
        'cpu': platform.processor(), 'cpu_info': Path('/proc/cpuinfo').read_text().split('\n\n')[0],
        'cpu_count': os.cpu_count(), 'available_affinity': sorted(os.sched_getaffinity(0)),
        'thread_environment': THREAD_ENV, 'loadavg': os.getloadavg(),
        'no_replacement_no_added_seed_no_retry': True, 'full_solver_calls': 0,
        'stage1_unchanged': True,
    }
    write(HERE / 'receipt.json', receipt)
    write(EXTERNAL / 'receipt.json', receipt)
    print(json.dumps({k: receipt[k] for k in ['source_hash', 'locked_files_verified', 'shared_files_verified', 'planned_trials']}))


if __name__ == '__main__':
    main()
