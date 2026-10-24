"""S1 campaign scheduling, at most ten serial single-core streams; no retries."""
import concurrent.futures
import fcntl
import hashlib
import json
import os
import resource
import signal
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
ROOT=Path(M['scratch'])
LOCK=threading.Lock()
ACTIVE=0
PEAK=0
DONE=0
STOP=threading.Event()
MIN_FREE=6*1024**3


class LowDisk(Exception):
    pass


def inventory(directory):
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file()}


def resume():
    """Discard only externally interrupted problems, once; never retry failures."""
    global DONE,PEAK
    events=[json.loads(line) for line in (ROOT/'events.jsonl').read_text().splitlines()]
    completed=[e['case_id'] for e in events if e['stage']=='problem_done']
    assert len(completed)==len(set(completed))
    assert not any(e['stage']=='campaign_done' for e in events)
    assert not (ROOT/'resume-started.json').exists(), 'Only one interruption restart authorized'
    interrupted=[]
    for task in M['inputs']:
        case=task['case_id'];d=ROOT/'runs'/case
        if case in completed or not d.exists():
            continue
        failures=[e for e in events if e.get('case_id')==case and
                  (e.get('returncode',0)!=0 or e.get('reason'))]
        for p in d.glob('*.ended.json'):
            if p.stat().st_size:
                r=json.loads(p.read_text())
                assert r['returncode']==0 and r['reason'] is None, (case,p)
        assert not failures, (case,failures)
        interrupted.append(case)
    state=dict(utc=datetime.now(timezone.utc).isoformat(),completed=completed,
        interrupted=interrupted,not_started=len(M['inputs'])-len(completed)-len(interrupted),
        reason='External /tmp capacity and sandbox interruption; excluded from results; restart once, not failure retry',
        original_events_sha256=hashlib.sha256((ROOT/'events.jsonl').read_bytes()).hexdigest(),
        original_events_bytes=(ROOT/'events.jsonl').stat().st_size,
        completed_files={k:v for case in completed for k,v in inventory(ROOT/'runs'/case).items()},
        interrupted_files={k:v for case in interrupted for k,v in inventory(ROOT/'runs'/case).items()})
    data=json.dumps(state,indent=2)+'\n'
    assert len(data.encode())<3_000_000
    with (ROOT/'resume-started.json').open('x') as f:
        f.write(data)
    archive=ROOT/'interrupted'/'attempt-0'
    archive.mkdir(parents=True,exist_ok=False)
    for case in interrupted:
        (ROOT/'runs'/case).rename(archive/case)
    DONE=len(completed)
    PEAK=max(e['active'] for e in events)
    event(stage='campaign_resume',completed_preserved=DONE,interrupted=interrupted,
          archive=str(archive),not_started=state['not_started'])
    return set(completed)


def event(**kw):
    global ACTIVE,PEAK,DONE
    with LOCK:
        if kw['stage'].endswith('_start') and kw['stage']!='campaign_start':
            ACTIVE+=1
        elif kw['stage'].endswith('_end'):
            ACTIVE-=1
        PEAK=max(PEAK,ACTIVE)
        assert 0<=ACTIVE<=10
        if kw['stage']=='problem_done':
            DONE+=1
        row=dict(utc=datetime.now(timezone.utc).isoformat(),loadavg=list(os.getloadavg()),active=ACTIVE,**kw)
        with (ROOT/'events.jsonl').open('a') as f:
            f.write(json.dumps(row)+'\n')
        if kw['stage'] in ('campaign_start','campaign_resume','campaign_paused','campaign_done','problem_done','disk_low'):
            with (OUT/'progress.md').open('a') as f:
                f.write(f"\n{row['utc']} {kw['stage']} {kw.get('case_id','')} 完了 {DONE}/266; active {ACTIVE}, peak {PEAK}; load1 {row['loadavg'][0]:.2f}。\n")


def kill(p):
    try:
        os.killpg(p.pid,signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        p.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL)
        p.wait()


def stage(task,cpu,mode,arm=None):
    # Every subprocess, including a continuation within a problem, is gated.
    with LOCK:
        free=shutil.disk_usage(ROOT).free
        if STOP.is_set() or free<MIN_FREE:
            STOP.set()
            low=True
        else:
            low=False
    if low:
        event(stage='disk_low',case_id=task['case_id'],mode=mode,arm=arm,
              free_bytes=free,minimum_free_bytes=MIN_FREE)
        raise LowDisk()
    case=task['case_id']
    d=ROOT/'runs'/case
    d.mkdir(parents=True,exist_ok=True)
    name=mode+('.'+arm if arm else '')
    # Exclusive receipt is created before launch. Never retry a started stage.
    with (d/(name+'.started.json')).open('x') as f:
        json.dump(dict(utc=datetime.now(timezone.utc).isoformat(),cpu=cpu),f)
    env={k:v for k,v in os.environ.items() if not k.startswith(('GEOSOLVER_ABLATE_','GEOSOLVER_S3_','GEOSOLVER_S7_'))}
    env.update(M['thread_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',PYTHONPATH=str(ROOT/'final/src'))
    if mode=='refine':
        env.update(M['switch_settings'][arm])
    cmd=['taskset','-c',str(cpu),M['python'],'-B',str(OUT/'worker.py'),str(ROOT),mode,case]
    if arm:
        cmd.append(arm)
    limit=180 if mode=='search' else (98 if mode=='refine' else 90)
    logpath=d/(name+'.log')
    event(case_id=case,stage=mode+'_start',arm=arm,cpu=cpu)
    started=time.monotonic()
    reason=None
    with logpath.open('w') as log:
        p=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        while p.poll() is None:
            if time.monotonic()-started>=limit or logpath.stat().st_size>=2_900_000:
                reason='outer_timeout' if time.monotonic()-started>=limit else 'log_size_limit'
                kill(p)
                break
            time.sleep(0.2)
        code=p.wait()
    receipt=dict(returncode=code,reason=reason,seconds=time.monotonic()-started,cpu=cpu,
                 mode=mode,arm=arm,environment={k:env[k] for k in env if k.startswith(('GEOSOLVER_','OMP_','OPENBLAS_','MKL_','NUMEXPR_','BLIS_','VECLIB_'))})
    (d/(name+'.ended.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    event(case_id=case,stage=mode+'_end',arm=arm,**{k:receipt[k] for k in ('cpu','returncode','reason','seconds')})
    return code==0 and reason is None


def stream(tasks,cpu):
    for task in tasks:
        if STOP.is_set():
            return
        try:
            problem(task,cpu)
        except LowDisk:
            return


def problem(task,cpu):
        searched=stage(task,cpu,'search')
        d=ROOT/'runs'/task['case_id']
        if searched and (d/'initial.pkl').exists():
            # Scale failure does not suppress either authorized refinement arm.
            stage(task,cpu,'scales')
            for arm in task['arm_order']:
                if stage(task,cpu,'refine',arm):
                    stage(task,cpu,'measure',arm)
        event(case_id=task['case_id'],stage='problem_done')


if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_FSIZE,(2_999_999,2_999_999))
    driver_lock=(ROOT/'driver.lock').open('a')
    fcntl.flock(driver_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for p,expected in M['files'].items():
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==expected,p
    assert set(sys.argv[1:]) <= {'--resume'}
    assert shutil.disk_usage(ROOT).free>=MIN_FREE, 'Less than 6 GiB free: no jobs started'
    if '--resume' in sys.argv:
        completed=resume()
    else:
        completed=set()
        with (ROOT/'started.json').open('x') as f:
            json.dump(dict(utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid()),f)
        event(stage='campaign_start')
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        jobs=[pool.submit(stream,[t for t in M['inputs'][i::10] if t['case_id'] not in completed],cpu)
              for i,cpu in enumerate(M['cpus'])]
        for job in jobs:
            job.result()
    if STOP.is_set():
        event(stage='campaign_paused',free_bytes=shutil.disk_usage(ROOT).free)
        sys.exit('Less than 6 GiB free: new jobs stopped; campaign incomplete')
    assert DONE==266
    event(stage='campaign_done')
    print('All 266 problems completed; peak',PEAK,flush=True)
