"""Short commands, at most two workers, never retry a started experiment slot."""
from __future__ import annotations
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from stage2_common import *


def prepare_jobs():
    assert not (RAW/'local-jobs.json').exists()
    audit=json.loads((OUT/'execution/lowering-audit.json').read_text())
    locals_=[];full=[]
    for p in audit:
        cid=p['id'];ready=[a for a in ARMS if p['arms'][a]['status']=='ready']
        rows=[]
        for k in range(200):
            rows.extend(dict(id=cid,arm=a,k=k,seed=410241) for a in sorted(ready,key=lambda a:order(cid,410241,a,k)))
        # Blocks respect each start's arm order; no block exceeds 147 seconds
        # of registered local + verification allowance (49 * 3 seconds).
        locals_.extend(rows[i:i+49] for i in range(0,len(rows),49))
        for seed in SEEDS:
            full.extend(dict(id=cid,arm=a,seed=seed) for a in sorted(ready,key=lambda a:order(cid,seed,a)))
    save(RAW/'local-jobs.json',locals_);save(RAW/'full-jobs.json',full)
    save(OUT/'execution/jobs.json',{'local_blocks':len(locals_),'local_slots':sum(map(len,locals_)),
         'full_jobs':len(full),'order_format':'Q41/order/v1|ID|seed|arm[|k]',
         'jobs':{str(p):digest(p) for p in [RAW/'local-jobs.json',RAW/'full-jobs.json']}})


def batch(kind):
    # This command lasts < 210 seconds even when both workers reach their cap.
    lock=(RAW/'batch.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    specs={'local':('local_stage2.py','local',165,'done.json'),
           'full':('full_stage2.py','full',200,'done.json'),
           'verify':('verify_full_stage2.py','full',200,'verification.json'),
           'scaling':('jacobian_stage2.py','scaling',205,'done.json'),
           'jacobian':('jacobian_stage2.py','jacobian',200,'done.json')}
    script,folder,cap,marker=specs[kind]
    jobs=json.loads((RAW/f'{"full" if kind=="verify" else kind}-jobs.json').read_text())
    (RAW/folder).mkdir(exist_ok=True)
    pending=[i for i in range(len(jobs)) if not (RAW/folder/f'{i:04d}'/marker).exists()]
    if kind=='verify':assert all((RAW/'full'/f'{i:04d}'/'done.json').exists() for i in range(len(jobs)))
    if not pending:
        print(json.dumps(dict(kind=kind,complete=True,total=len(jobs))));return
    cpus=sorted(os.sched_getaffinity(0))[-2:]
    running=[]
    for lane,index in enumerate(pending[:2]):
        d=RAW/folder/f'{index:04d}';d.mkdir(exist_ok=True)
        receipt=d/'launched.json'
        # Resumption of a local block runs only unstarted slots. A launched
        # full job without a final receipt is interrupted and never repeated.
        if kind in ('full','jacobian') and receipt.exists():
            save(d/'done.json',dict(jobs[index],interrupted=True,T=180,censored=True,
                                  status='NA',reason='interrupted_no_retry',finished_utc=utc()))
            continue
        log=(RAW/'logs'/f'{kind}-{index:04d}.log').open('a')
        launch=dict(index=index,utc=utc(),cpu=cpus[lane],cwd=str(CLEAN),kind=kind)
        if not receipt.exists():save(receipt,launch)
        else:append(d/'launch-history.jsonl',launch)
        argument=f'scale:{index}' if kind=='scaling' else str(index)
        proc=subprocess.Popen([PYTHON,'-B',str(OUT/script),argument],cwd=CLEAN,env=environment(),
                              stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                              preexec_fn=lambda cpu=cpus[lane]:os.sched_setaffinity(0,{cpu}))
        running.append((index,proc,log,time.monotonic()))
    while running:
        for entry in list(running):
            index,proc,log,t=entry
            if proc.poll() is None and time.monotonic()-t<cap:continue
            if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL)
            rc=proc.wait();log.close();running.remove(entry)
            append(OUT/'execution/batches.jsonl',dict(kind=kind,index=index,returncode=rc,
                   seconds=time.monotonic()-t,utc=utc(),load=os.getloadavg()))
            print(json.dumps(dict(kind=kind,index=index,returncode=rc,seconds=time.monotonic()-t)),flush=True)
            if rc and kind=='full' and not (RAW/folder/f'{index:04d}'/'done.json').exists():
                save(RAW/folder/f'{index:04d}'/'done.json',dict(jobs[index],T=180,censored=True,
                       reason='process_failure_no_retry',returncode=rc,finished_utc=utc()))
            if rc and kind=='local':
                # Do not automatically continue after an implementation error.
                # The starts ledger distinguishes lost from unstarted slots.
                print('local process failed; inspect before next command',flush=True)
            if rc and kind=='jacobian' and not (RAW/folder/f'{index:04d}'/'done.json').exists():
                save(RAW/folder/f'{index:04d}'/'done.json',dict(jobs[index],status='NA',
                    reason='process_failure_no_retry',returncode=rc,finished_utc=utc()))
            if rc and kind in ('scaling','verify'):
                print(f'{kind} process failed; inspect before next command',flush=True)
        time.sleep(.1)
    count=sum((RAW/folder/f'{i:04d}'/marker).exists() for i in range(len(jobs)))
    print(json.dumps(dict(kind=kind,completed=count,total=len(jobs),complete=count==len(jobs))),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare-jobs':prepare_jobs()
    else:batch(sys.argv[1])
