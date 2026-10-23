"""Bounded, resumable campaign: <=3 numerical workers; one invocation <=~150s."""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]

def verify():
    lock=json.loads((OUT/'prediction.lock.json').read_text())
    effective=dict(lock['files'])
    for path in sorted((OUT/'amendments').glob('amendment-*.json')):
        amendment=json.loads(path.read_text())
        for rel,change in amendment['changes'].items():
            assert effective[rel]==change['before_sha256'],rel
            assert hashlib.sha256((OUT/change['before_file']).read_bytes()).hexdigest()==change['before_sha256'],rel
            effective[rel]=change['after_sha256']
    for rel,h in effective.items():
        assert hashlib.sha256((OUT/rel).read_bytes()).hexdigest()==h,rel
    source=json.loads((OUT/'source-manifest.json').read_text())
    for rel,h in source['files'].items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==h,rel
    assert lock['prediction_sha256']==hashlib.sha256((OUT/'prediction.md').read_bytes()).hexdigest()

def one(task):
    case,seed,k=task
    log=OUT/'logs'/case/f'{seed}-{k}.log'; log.parent.mkdir(parents=True,exist_ok=True)
    env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(ROOT/'src'),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
    cmd=[sys.executable,'-B',str(OUT/'experiment.py'),case,str(seed),str(k)]
    t=time.monotonic()
    with log.open('w') as f:
        try:
            r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=85)
            status=r.returncode
        except subprocess.TimeoutExpired: status='timeout'
    return {'task':task,'status':status,'seconds':time.monotonic()-t,'experiment_sha256':hashlib.sha256((OUT/'experiment.py').read_bytes()).hexdigest()}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--seconds',type=float,default=135); ap.add_argument('--max-tasks',type=int,default=9999)
    a=ap.parse_args(); assert 90<=a.seconds<=160
    verify()
    selected=json.loads((OUT/'selection.json').read_text())
    tasks=[]; partial=[]; complete=0
    # Breadth first: every problem is represented before subsequent starts.
    for k in range(8):
        for seed in [32001,32002]:
            for c in selected:
                task=(c['id'],seed,k); path=OUT/'runs'/c['id']/f'{seed}-{k}.json'
                if path.exists():
                    if json.loads(path.read_text()).get('complete'): complete+=1
                    else: partial.append(task)
                    continue
                if (OUT/'logs'/c['id']/f'{seed}-{k}.log').exists(): partial.append(task); continue
                tasks.append(task)
    start=time.monotonic(); receipts=[]
    print(json.dumps({'complete_before':complete,'pending':len(tasks),'partial':partial,'max_workers':3}),flush=True)
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        active={}; launched=0
        while active or tasks:
            while tasks and len(active)<3 and launched<a.max_tasks and (time.monotonic()-start<a.seconds-85 or launched<3):
                task=tasks.pop(0); active[pool.submit(one,task)]=task; launched+=1
            if not active: break
            done,_=cf.wait(active,return_when=cf.FIRST_COMPLETED)
            for future in done:
                receipt=future.result(); receipts.append(receipt); active.pop(future)
                print(json.dumps(receipt),flush=True)
    receipt={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'seconds':time.monotonic()-start,'workers_max':3,'runs':receipts}
    folder=OUT/'receipts'; folder.mkdir(exist_ok=True)
    (folder/f'chunk-{time.time_ns()}.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'chunk_seconds':receipt['seconds'],'tasks':len(receipts),'remaining_unlaunched':len(tasks)}),flush=True)

if __name__=='__main__': main()
