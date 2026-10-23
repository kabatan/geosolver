"""Sequential cold worker runs; bounded resources, no network or external writes."""
from pathlib import Path
import json,sys,subprocess,os,time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
coh=json.loads((HERE/'cohorts.json').read_text())
phase=sys.argv[1]
if phase=='positive_first':jobs=[(cid,arm,4301) for cid in coh['positive_development'] for arm in ['C1','C2','C3']]
elif phase=='positive_repeat':jobs=[(cid,arm,seed) for seed in [4302,4303] for cid in coh['positive_development'] for arm in ['C2','C1']]
elif phase=='zero':jobs=[(cid,arm,4301) for cid in coh['zero_candidates'] for arm in ['C1','C2','C3']]
else:raise ValueError(phase)
env=dict(os.environ,PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'src'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(HERE/'tmp'))
(HERE/'tmp').mkdir(exist_ok=True)
for cid,arm,seed in jobs:
 out=HERE/'runs'/f'{cid}__{arm}__{seed}'
 if (out/'result.json').exists():
  data=json.loads((out/'result.json').read_text())
  if data['status']!='running':print('existing',cid,arm,seed,data['status'],flush=True);continue
  raise RuntimeError('unfinished existing trial '+str(out))
 t0=time.monotonic()
 try:
  p=subprocess.run([sys.executable,'-B',str(HERE/'experiment.py'),cid,arm,str(seed)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=190)
  print(p.stdout.strip(),flush=True)
  if p.stderr:print('stderr',p.stderr[-800:],flush=True)
  (out/'process.json').write_text(json.dumps({'returncode':p.returncode,'cold_process_seconds':time.monotonic()-t0,'stderr':p.stderr[-2000:]},indent=2))
 except subprocess.TimeoutExpired:
  out.mkdir(exist_ok=True,parents=True)
  r=json.loads((out/'result.json').read_text()) if (out/'result.json').exists() else {'id':cid,'arm':arm,'seed':seed}
  r.update(status='process_timeout',seconds=190);(out/'result.json').write_text(json.dumps(r,indent=2));print(cid,arm,seed,'process_timeout',flush=True)
