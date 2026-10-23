"""Persistent, offline Julia worker with hard per-job deadlines."""
import hashlib
import json
import os
import selectors
import subprocess
import time
from pathlib import Path

OUT=Path(__file__).resolve().parent
BINARY='/home/kabatan/.julia/juliaup/julia-1.12.6+0.x64.linux.gnu/bin/julia'
env=dict(os.environ,JULIA_LOAD_PATH=f'{OUT}/runtime/packages:@stdlib',
         JULIA_DEPOT_PATH=f'{OUT}/runtime/depot:/home/kabatan/.julia',
         JULIA_PKG_OFFLINE='true',JULIA_PKG_PRECOMPILE_AUTO='0',JULIA_NUM_THREADS='1',
         OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TMPDIR=f'{OUT}/runtime/tmp')
(OUT/'hc-runs').mkdir(exist_ok=True)
meta={'start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'jobs':[],'packages_installed':0}
meta['hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [OUT/'protocol.md',OUT/'prepared.json',OUT/'serve.jl',Path(__file__)]}
log=(OUT/'hc-stderr.log').open('w')
p=subprocess.Popen([BINARY,'--startup-file=no','--history-file=no','--compiled-modules=existing',
                    '--pkgimages=existing','--threads=1,0','--gcthreads=1',str(OUT/'serve.jl')],
                   cwd=OUT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,
                   text=True,bufsize=1)
sel=selectors.DefaultSelector()
sel.register(p.stdout,selectors.EVENT_READ)

def response(seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if sel.select(max(0,deadline-time.monotonic())):
            line=p.stdout.readline()
            if not line:
                raise RuntimeError(f'Julia exited ({p.poll()})')
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                with (OUT/'hc-stdout-extra.log').open('a') as f: f.write(line)
    raise TimeoutError(f'Julia response exceeded {seconds}s')

def send(job,seconds):
    p.stdin.write(json.dumps(job)+'\n');p.stdin.flush()
    return response(seconds)

t0=time.monotonic()
try:
    meta['environment']=response(180)
    meta['load_seconds']=time.monotonic()-t0
    print('environment',meta['environment'],flush=True)
    t=time.monotonic()
    meta['warmup']=send({'event':'warmup'},180)
    meta['warmup_seconds']=time.monotonic()-t
    if meta['warmup'].get('event')!='warmup_done':
        raise RuntimeError(str(meta['warmup']))
    for data in json.loads((OUT/'prepared.json').read_text()):
        if not data.get('eligible'): continue
        for method in ['total_degree','polyhedral']:
            for seed in [211023,211024]:
                job={'input':str(OUT/'inputs'/f"{data['id']}__{data['mode']}.json"),
                     'method':method,'seed':seed}
                t=time.monotonic()
                result=send(job,60)
                result.update(id=data['id'],mode=data['mode'],method=method,seed=seed,
                              outer_job_seconds=time.monotonic()-t)
                path=OUT/'hc-runs'/f"{data['id']}__{data['mode']}__{method}__{seed}.json"
                path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
                meta['jobs'].append({k:v for k,v in result.items() if k not in ['paths','solutions']})
                print(json.dumps(meta['jobs'][-1],ensure_ascii=False),flush=True)
                (OUT/'hc-execution.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
except Exception as e:
    meta['execution_error']=f'{type(e).__name__}: {e}'
    print(meta['execution_error'],flush=True)
finally:
    meta['elapsed_seconds']=time.monotonic()-t0
    if p.poll() is None:
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    meta['return_code']=p.returncode
    (OUT/'hc-execution.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    log.close()
