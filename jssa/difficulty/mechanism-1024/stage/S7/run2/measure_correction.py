"""Measure saved candidates only; never invoke search/refine or retry a job."""
import concurrent.futures
import fcntl
import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
M = json.loads((OUT / 'pre-run-hashes.json').read_text())
ROOT = Path(M['scratch'])
MIN_FREE = 6 * 1024**3
SMOKE = ['AIME-2006-I-01', 'AIME-2006-II-01', 'AIME-2006-II-06']
LOCK = threading.Lock()
STOP = threading.Event()
ACTIVE = PEAK = 0


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text()) if p.exists() else None


def save(p, obj):
    text = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert len(text.encode()) < 3_000_000
    with p.open('x') as f:
        f.write(text)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def original_path(p):
    return p.with_name(p.name.replace('.measure.json', '.measure.original.json'))


def check_hashes():
    update = read(OUT / 'hash-update-history.json')['updates'][-1]
    assert update['kind'] == 'measure-only-correction'
    for path, expected in update['evaluation_files'].items():
        assert sha(Path(path)) == expected, path


def eligible(case, arm):
    d = ROOT / 'runs' / case
    r = read(d / ('refine.' + arm + '.ended.json'))
    return bool(r and r['returncode'] == 0 and r['reason'] is None
                and (d / (arm + '.refined.pkl')).exists())


def prepare():
    assert shutil.disk_usage('/tmp').free >= MIN_FREE
    events = [json.loads(s) for s in (ROOT / 'events.jsonl').read_text().splitlines()]
    assert events[-1]['stage'] == 'campaign_done'
    files = {str(p.relative_to(ROOT)): sha(p) for p in sorted(ROOT.rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts}
    skipped = [dict(case_id=t['case_id'], arm=a,
                    refinement_receipt=read(ROOT / 'runs' / t['case_id'] / ('refine.'+a+'.ended.json')))
               for t in M['inputs'] for a in ('BASE', 'RAW') if not eligible(t['case_id'], a)]
    save(ROOT / 'measure-correction-baseline.json', dict(utc=stamp(), files=files, skipped=skipped,
         old_answer_sha256=sha(OUT/'answer-measure-failed.md'), population=266,
         smoke_cases=SMOKE, parallel=8, cpus=M['cpus'][:8]))
    print('Prepared immutable baseline; ineligible arms:', len(skipped), flush=True)


def run_one(case, arm, cpu):
    global ACTIVE, PEAK
    d = ROOT / 'runs' / case
    if not eligible(case, arm):
        return
    name = 'measure-corrected.' + arm
    if (d / (name + '.started.json')).exists():
        end = read(d / (name + '.ended.json'))
        assert end and end['returncode'] == 0 and end['reason'] is None, (case, arm, 'no retry')
        return
    with LOCK:
        if STOP.is_set() or shutil.disk_usage('/tmp').free < MIN_FREE:
            STOP.set()
            raise RuntimeError('/tmp free below 6 GiB: stopped')
        save(d / (name + '.started.json'), dict(utc=stamp(), cpu=cpu, refined_sha256=sha(d/(arm+'.refined.pkl'))))
        old = d / (arm + '.measure.json')
        if old.exists():
            assert not original_path(old).exists()
            old.rename(original_path(old))
        ACTIVE += 1
        PEAK = max(PEAK, ACTIVE)
        assert ACTIVE <= 8
    env = {k:v for k,v in os.environ.items() if not k.startswith(('GEOSOLVER_ABLATE_', 'GEOSOLVER_S3_', 'GEOSOLVER_S7_'))}
    env.update(M['thread_environment'])
    env.update(PYTHONPATH=str(ROOT/'final/src'), PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1', TMPDIR='/tmp')
    cmd = ['taskset', '-c', str(cpu), M['python'], '-B', str(OUT/'worker.py'), str(ROOT), 'measure', case, arm]
    reason = None
    started = time.monotonic()
    observations = set()
    with (d/(name+'.log')).open('x') as log:
        p = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        while p.poll() is None:
            try:
                status = Path(f'/proc/{p.pid}/status').read_text()
                threads = int(next(s.split(':')[1] for s in status.splitlines() if s.startswith('Threads:')))
                affinity = tuple(sorted(os.sched_getaffinity(p.pid)))
                if (d/(name+'.runtime-start.json')).exists():
                    observations.add((threads, affinity))
                if (d/(name+'.runtime-start.json')).exists() and (threads != 1 or affinity != (cpu,)):
                    reason = 'execution_contract_violation'
            except (FileNotFoundError, ProcessLookupError):
                pass
            if shutil.disk_usage('/tmp').free < MIN_FREE:
                STOP.set()
                reason = 'low_disk'
            if time.monotonic()-started >= 90:
                reason = 'outer_timeout'
            if (d/(name+'.log')).stat().st_size >= 2_900_000:
                reason = 'log_size_limit'
            if reason:
                os.killpg(p.pid, signal.SIGKILL)
                break
            time.sleep(.05)
        code = p.wait()
    with LOCK:
        ACTIVE -= 1
    end = dict(utc=stamp(), case_id=case, arm=arm, cpu=cpu, pid=p.pid, returncode=code,
               reason=reason, seconds=time.monotonic()-started,
               environment={k:env[k] for k in M['thread_environment']},
               observations=[dict(threads=n, affinity=list(a)) for n,a in sorted(observations)])
    save(d/(name+'.ended.json'), end)
    assert code == 0 and reason is None, end
    for which in ('start', 'end'):
        receipt = read(d/(name+'.runtime-'+which+'.json'))
        assert receipt['threads'] == 1 and receipt['affinity'] == [cpu], receipt
    assert (d/(arm+'.measure.json')).is_file()


def run(mode):
    check_hashes()
    if mode == 'all':
        assert read(ROOT/'measure-correction-smoke.json')['passed']
    tasks = [(t['case_id'], a) for t in M['inputs'] for a in t['arm_order']
             if mode == 'all' or t['case_id'] in SMOKE]
    def stream(items, cpu):
        for case, arm in items:
            run_one(case, arm, cpu)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(stream, tasks[i::8], cpu) for i,cpu in enumerate(M['cpus'][:8])]
        for f in futures:
            f.result()
    if mode == 'smoke':
        # Only digit sanity and evaluation errors; do not compute/read any W judgment.
        results = []
        for case in SMOKE:
            for arm in ('BASE', 'RAW'):
                rows = read(ROOT/'runs'/case/(arm+'.measure.json'))['rows']
                valid = [r['error_digits'] for r in rows if 'error_digits' in r]
                assert valid and all(math.isfinite(v) and v <= 600 for v in valid)
                assert not any('HighPrecisionContaminationError' in r.get('answer_error','') for r in rows)
                results.append(dict(case_id=case, arm=arm, rows=len(rows), measured=len(valid),
                                    digits_min=min(valid), digits_max=max(valid)))
        save(ROOT/'measure-correction-smoke.json', dict(utc=stamp(), passed=True, results=results,
              policy='digit sanity only; no W values inspected'))
        print(json.dumps(results), flush=True)
    save(ROOT/('measure-correction-'+mode+'-done.json'), dict(utc=stamp(), peak_parallel=PEAK, active=ACTIVE))
    print(mode, 'complete, all subprocesses waited; peak', PEAK, flush=True)


def audit():
    check_hashes()
    baseline = read(ROOT/'measure-correction-baseline.json')
    changed = []
    for path, expected in baseline['files'].items():
        p = ROOT/path
        if p.name.endswith('.measure.json') and original_path(p).exists():
            p = original_path(p)
        if sha(p) != expected:
            changed.append(path)
    assert not changed, changed
    assert sha(OUT/'answer-measure-failed.md') == baseline['old_answer_sha256']
    receipts = []
    skipped = []
    for t in M['inputs']:
        for arm in ('BASE', 'RAW'):
            case = t['case_id']; d = ROOT/'runs'/case
            end = read(d/('measure-corrected.'+arm+'.ended.json'))
            if eligible(case, arm):
                assert end and end['returncode'] == 0 and end['reason'] is None
                assert all(o['threads']==1 and o['affinity']==[end['cpu']] for o in end['observations'])
                assert read(d/('measure-corrected.'+arm+'.started.json'))['refined_sha256'] == sha(d/(arm+'.refined.pkl'))
                assert original_path(d/(arm+'.measure.json')).is_file()
                receipts.append(end)
            else:
                assert end is None and not (d/(arm+'.measure.json')).exists()
                skipped.append(dict(case_id=case,arm=arm))
    assert len(receipts)+len(skipped)==532
    done=read(ROOT/'measure-correction-all-done.json')
    assert done['active']==0 and done['peak_parallel']<=8
    save(ROOT/'measure-correction-audit.json', dict(utc=stamp(), passed=True, population=266,
         measured_jobs=len(receipts), skipped=skipped, original_files_verified=len(baseline['files']),
         changed_original_files=changed, search_reruns=0, refine_reruns=0,
         peak_parallel=done['peak_parallel'], execution_contract_status='pass',
         all_processes_waited=True, smoke=read(ROOT/'measure-correction-smoke.json')))
    print('Correction audit passed; jobs',len(receipts),'skipped',len(skipped),flush=True)


if __name__ == '__main__':
    lock = (ROOT/'measure-correction.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert shutil.disk_usage('/tmp').free >= MIN_FREE, '/tmp free below 6 GiB'
    mode = sys.argv[1]
    if mode == 'prepare': prepare()
    elif mode in ('smoke','all'): run(mode)
    elif mode == 'audit': audit()
    else: raise ValueError(mode)
