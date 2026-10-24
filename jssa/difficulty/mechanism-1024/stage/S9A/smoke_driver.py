"""Only four <=10 s smoke calls. No search, measure, verify or campaign mode."""
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    m = json.loads((OUT / 'pre-smoke-hashes.json').read_text())
    s = json.loads((OUT / 'source-hashes.json').read_text())
    c = json.loads((OUT / 'configs.json').read_text())
    for path, expected in m['files_sha256'].items():
        assert sha(OUT / path) == expected, path
    for root_key, files_key in [('base_source', 'base_files_sha256'),
                                ('patched_source', 'patched_files_sha256'),
                                ('frozen_source', 'frozen_files_sha256')]:
        root = Path(s[root_key])
        actual = {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
                  if p.is_file() and '__pycache__' not in p.parts}
        assert actual == s[files_key], root_key
    assert sha(m['initial_path']) == m['initial_sha256']
    assert sha(m['input_path']) == m['input_sha256']
    dest = OUT / 'smoke'
    dest.mkdir(exist_ok=False)  # Never silently repeat or replace smoke evidence.
    jobs = []
    cpu = sorted(os.sched_getaffinity(0))[0]
    for arm, switches in c['arms'].items():
        env = {k: v for k, v in os.environ.items() if not k.startswith('GEOSOLVER_ABLATE_')}
        env.update(c['thread_environment'])
        env.update(switches)
        env.update(PYTHONPATH=str(Path(s['patched_source']) / 'src'),
                   PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
        cmd = ['taskset', '-c', str(cpu), m['python'], '-B', str(OUT / 'smoke_worker.py'), arm]
        start = time.monotonic()
        process = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=c['smoke']['outer_seconds'])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        jobs.append(dict(arm=arm, process_seconds=time.monotonic() - start,
                         outer_timeout=timed_out, returncode=process.returncode, cpu=cpu))
        (dest / 'driver.json').write_text(json.dumps(dict(max_parallel=1, jobs=jobs), indent=2) + '\n')
    # Only routing and damping are checked. No numerical quality field is accessed.
    rows = {arm: json.loads((dest / (arm + '.json')).read_text()) for arm in c['arms']}
    for arm, row in rows.items():
        assert row['process_state'] != 'exception', (arm, row.get('exception_type'))
        assert row['calls'].get('_run_stage') == 1
    assert rows['R0']['calls'].get('compute_levenberg_marquardt_step', 0) > 0
    assert rows['R0']['adaptive_lambda_update_lines'] > 0
    assert len(rows['R0']['lambda_values']) > 1
    assert rows['R1']['calls'].get('compute_levenberg_marquardt_step', 0) > 0
    assert rows['R1']['lambda_values'] == ['0.0']
    assert rows['R1']['adaptive_lambda_update_lines'] == 0
    assert rows['R2']['calls'].get('compute_levenberg_marquardt_step', 0) > 0
    assert len(rows['R2']['lambda_values']) == 1
    assert rows['R2']['lambda_values'][0] != '0.0'
    assert rows['R2']['adaptive_lambda_update_lines'] == 0
    assert rows['R3']['calls'].get('compute_levenberg_marquardt_step', 0) == 0
    assert rows['R3']['calls'].get('run_line_search', 0) == 0
    assert rows['R3']['calls'].get('_run_findroot_closure', 0) > 0
    assert rows['R3']['newton_linear_step_attempts'] > 0
    (dest / 'checks.json').write_text(json.dumps(dict(routing_and_damping_checks_passed=True,
        quality_inspected=False, measurement_run=False, retries=0), indent=2) + '\n')
    print('Four smoke calls finished; routing and damping assertions passed; quality not inspected.')


if __name__ == '__main__':
    main()
