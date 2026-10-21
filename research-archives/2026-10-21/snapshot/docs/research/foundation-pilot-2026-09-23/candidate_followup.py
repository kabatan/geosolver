"""Adaptive confirmation of the promising native non-thinking 9B setting."""
import json,subprocess,sys,time
from pathlib import Path
D=Path(__file__).resolve().parent;R=Path('qwen/.runtime/foundation_pilot_20260923')
while True:
 p=R/'target-after-qwen3_4b/receipt.json'
 if p.exists():
  r=json.loads(p.read_text())
  if r['status']!='running':
   assert r['status']=='complete',r
   break
 time.sleep(10)
for phase,jobs,cap in [('direct-confirmation','confirmation-jobs.json',8192),('direct-target','target-dev-jobs.json',32768)]:
 cmd=[sys.executable,str(D/'infer_batch.py'),'--key','qwen35_9b','--phase',phase,'--jobs',str(D/jobs),'--cap',str(cap),'--context',str(cap+4096),'--non-thinking']
 print('Starting '+phase,flush=True);subprocess.run(cmd,check=True)
print('Candidate confirmation complete.',flush=True)
