"""One explicitly authorized cause-only run; never grade or inspect answers."""
import os
from pathlib import Path
import sys
import time

from measurement_common import HERE, load, save, sha, utc
from measurement_runtime import Job, selected_environment


def main():
    audit = HERE.parent / 'rerun-audit'
    out = audit / 'diagnostic-0578'
    out.mkdir()
    (out / 'receipts').mkdir()
    raw = Path('/tmp/mechanism-S8-fsize-diagnostic-0578')
    raw.mkdir()
    old = HERE.parent / 'run-superpc'
    freeze = load(old / 'measurement-freeze.json')
    spec = next(j for j in freeze['jobs'] if j['queue_index'] == 578)
    original = load(old / 'receipts/0578.start.json')
    assert spec['time_limit_seconds'] == 180 and spec['cores'] == 1
    assert sha(Path(freeze['python']).resolve()) == freeze['python_sha256']
    freeze = dict(freeze, raw_root=str(raw))
    job = Job(spec, original['cpu'], out, raw, freeze)
    assert selected_environment(job.env) == original['actual_environment']
    assert job.command[:2] == original['command'][:2]
    assert job.command[3:-1] == original['command'][3:-1]
    observed = {}
    stderr_tails = {}
    limits = {}
    while True:
        # Observe worker temporary-file sizes and stderr without reading answers.
        for proc in job.processes():
            try:
                limits[str(proc.pid)] = Path(f'/proc/{proc.pid}/limits').read_text()
                cwd = Path(proc.cwd())
                if not cwd.name.startswith('geosolver-') or cwd.parent != Path('/tmp'):
                    continue
                for p in cwd.iterdir():
                    if p.is_file():
                        stat = p.stat()
                        observed[str(p)] = max(stat.st_size, observed.get(str(p), 0))
                        if p.name == 'stderr.log':
                            with p.open('rb') as stream:
                                stream.seek(max(0, stat.st_size - 8000))
                                stderr_tails[str(p)] = stream.read().decode(errors='replace')
            except (OSError, Exception) as error:
                # Process disappearance between observations is expected.
                if type(error).__name__ not in ('NoSuchProcess', 'ZombieProcess', 'FileNotFoundError', 'ProcessLookupError'):
                    raise
        now = time.monotonic()
        if now >= job.deadline:
            receipt = job.finish('timeout', 180.0)
            break
        if job.proc is None or job.proc.poll() is not None:
            receipt = job.finish('completed' if job.proc else 'spawn_failure', now-job.t0)
            break
        if now >= job.next_sample:
            job.sample()
            if 'tree_memory_limit' in job.violations:
                receipt = job.finish('memory_limit', now-job.t0)
                break
        time.sleep(.01)
    result = raw / '0578/result.json'
    error = None
    result_stderr_tail = ''
    json_valid = False
    if result.exists():
        data = load(result)
        json_valid = True
        error = data.get('error')
        result_stderr_tail = str(data.get('diagnostics', {}).get('stderr', ''))[-8000:]
        del data  # No status, answers, reference, or correctness inspection.
    outer_tails = {}
    for p in (raw / '0578').glob('stderr.log.*'):
        with p.open('rb') as stream:
            stream.seek(max(0, p.stat().st_size-8000))
            outer_tails[str(p)] = stream.read().decode(errors='replace')
    save(out / 'cause-only.json', dict(
        utc=utc(), measurement_eligible=False, correctness_inspected=False,
        solver_calls=1, queue_index=578, case_id=spec['case_id'],
        configuration=spec['configuration'], seed=spec['seed'],
        cpu=original['cpu'], time_limit_seconds=180, cores=1,
        environment_matches_original=True, only_contract_change='RLIMIT_FSIZE=1073741824',
        original_exit_code=2, original_error=dict(code='artifact_missing', message='worker exited with code 1 without an artifact'),
        new_exit_code=receipt['exit_code'], state=receipt['state'],
        wall_seconds=receipt['wall_seconds'], resource_violations=receipt['resource_violations'],
        result_json_valid=json_valid, new_error=error,
        result_size_bytes=result.stat().st_size if result.exists() else None,
        observed_worker_file_sizes=observed, observed_process_limits=limits,
        worker_stderr_tails=stderr_tails, outer_stderr_tails=outer_tails,
        result_stderr_tail=result_stderr_tail,
        raw_directory=str(raw), launch_sha256=sha(HERE/'measurement_launch.py')))
    print('Cause-only evidence saved:', out/'cause-only.json', flush=True)
    print('exit=', receipt['exit_code'], 'state=', receipt['state'], 'error=', error, flush=True)


if __name__ == '__main__':
    main()
