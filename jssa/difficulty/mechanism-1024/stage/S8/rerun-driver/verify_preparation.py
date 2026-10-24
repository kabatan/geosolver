"""Read-only Linux/WSL preflight. Never calls solve/EngineRunner/optimize."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--repo-root', type=Path, default=HERE.parents[4])
    parser.add_argument('--machine', choices=['superPC', 'WinPC'], required=True)
    args = parser.parse_args()
    if (HERE / 'hashes.json').exists():
        fixed = json.loads((HERE / 'hashes.json').read_text())
        for name, expected in fixed['artifact_files_sha256'].items():
            assert sha(HERE / name) == expected, ('artifact changed', name)
    sys.path.insert(0, str(args.source_root.resolve() / 'src'))
    from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock
    source = json.loads((HERE / 'source-hashes.json').read_text())
    assert source_tree_hash() == source['source_hash']
    assert verify_engine_lock() == (True, source['source_hash'])
    for name, expected in source['files_sha256'].items():
        assert sha(args.source_root / name) == expected, name
    configs = json.loads((HERE / 'configs.json').read_text())
    assignment = json.loads((HERE / 'assignment.json').read_text())
    plan = json.loads((HERE / 'run-plan.json').read_text())
    assert not plan['execution_authorized']
    assert len(configs['configurations']) == 12 and configs['aliases'] == {'N+1': 'C1'}
    problems = assignment['problems']
    assert len(problems) == len({r['case_id'] for r in problems}) == 106
    for i, row in enumerate(problems):
        assert row['assignment_sha256'] == hashlib.sha256(row['case_id'].encode()).hexdigest()
        assert row['sha256_rank'] == i
        assert row['machine'] == ('superPC' if i % 2 == 0 else 'WinPC')
        assert sha(args.repo_root / row['dsl_path']) == row['input_sha256'], row['case_id']
    assert problems == sorted(problems, key=lambda r: (r['assignment_sha256'], r['case_id']))
    config_names = [c['name'] for c in configs['configurations']]
    expected_jobs = []
    for row in problems:
        for seed in (601, 602, 603):
            offset = (row['sha256_rank'] + seed - 601) % 12
            for name in config_names[offset:] + config_names[:offset]:
                expected_jobs.append(dict(queue_index=len(expected_jobs), case_id=row['case_id'],
                    machine=row['machine'], dsl_path=row['dsl_path'], input_sha256=row['input_sha256'],
                    seed=seed, configuration=name, time_limit_seconds=180, cores=1))
    assert plan['jobs'] == expected_jobs and len(expected_jobs) == 3816
    assert sys.version_info[:2] == (3, 12)
    installed, absent = {}, []
    for name, expected in source['dependency_lock']['packages'].items():
        try:
            installed[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            assert name == 'colorama' and sys.platform == 'linux', ('missing', name)
            absent.append(name)
            continue
        assert installed[name] == expected, (name, installed[name], expected)
    import PyNomad
    print(json.dumps(dict(preflight_only=True, solver_executions=0, machine=args.machine,
        source_hash=source_tree_hash(), engine_lock_valid=True, all_inputs_valid=True,
        planned_jobs_on_this_machine=sum(j['machine'] == args.machine for j in plan['jobs']),
        python=sys.executable, python_realpath=str(Path(sys.executable).resolve()),
        python_sha256=sha(Path(sys.executable).resolve()), python_version=sys.version,
        installed_dependencies=installed, absent_platform_only_dependencies=absent,
        PyNomad_file=PyNomad.__file__, host=platform.node(), platform=platform.platform(),
        eligible_cpus=sorted(os.sched_getaffinity(0))), ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
