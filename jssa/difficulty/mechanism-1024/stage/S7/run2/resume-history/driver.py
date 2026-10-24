"""S1 campaign scheduling, at most ten serial single-core streams; no retries."""
import concurrent.futures
import hashlib
import json
import os
import resource
import signal
import subprocess
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
        if kw['stage'] in ('campaign_start','campaign_done','problem_done'):
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
    for p,expected in M['files'].items():
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==expected,p
    with (ROOT/'started.json').open('x') as f:
        json.dump(dict(utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid()),f)
    event(stage='campaign_start')
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        jobs=[pool.submit(stream,M['inputs'][i::10],cpu) for i,cpu in enumerate(M['cpus'])]
        for job in jobs:
            job.result()
    event(stage='campaign_done')
    print('All 266 problems completed; peak',PEAK,flush=True)
