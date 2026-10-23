"""Four bounded workers, paired A/B sequential within each case."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os,sys,json,subprocess,time,hashlib,datetime
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
lock=json.loads((HERE/'registration-lock.json').read_text())
assert hashlib.sha256((HERE/'preregistration.md').read_bytes()).hexdigest()==lock['preregistration_sha256']
env=dict(os.environ,PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'src'),
         OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(HERE/'tmp'))
def job(item):
    idx,cid=item
    for arm in (['A','B'] if idx%2==0 else ['B','A']):
        out=HERE/'runs'/f'{cid}__{arm}'
        if out.exists():raise RuntimeError('preserve existing trial '+str(out))
        t0=time.monotonic();utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            p=subprocess.run([sys.executable,'-B',str(HERE/'experiment.py'),cid,arm],cwd=ROOT,env=env,capture_output=True,text=True,timeout=130)
            proc=dict(returncode=p.returncode,cold_seconds=time.monotonic()-t0,started_utc=utc,stderr=p.stderr[-4000:],stdout=p.stdout[-4000:])
            print(p.stdout.strip() or json.dumps(dict(id=cid,arm=arm,error=p.stderr[-400:])),flush=True)
        except subprocess.TimeoutExpired as e:
            proc=dict(returncode='process_timeout',cold_seconds=time.monotonic()-t0,started_utc=utc)
        out.mkdir(exist_ok=True,parents=True)
        (out/'process.json').write_text(json.dumps(proc,indent=2)+'\n')
        rp=out/'result.json'
        data=json.loads(rp.read_text()) if rp.exists() else dict(id=cid,arm=arm)
        if data.get('status') in [None,'running']:
            data.update(status='process_timeout' if proc['returncode']=='process_timeout' else 'process_error',seconds=proc['cold_seconds'])
            rp.write_text(json.dumps(data,indent=2)+'\n')
with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(job,enumerate(lock['ids'])))
