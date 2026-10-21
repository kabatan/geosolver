"""One bounded control/prompt/FT comparison, serialized with the model screen."""
import json,subprocess,sys,time
from pathlib import Path
from qwen.grpo_run import run_worker
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/foundation_pilot_20260923')
while True:
 p=R/'screen-corrected-r1_8b/receipt.json'
 if p.exists():
  r=json.loads(p.read_text())
  if r['status']!='running':
   assert r['status']=='complete',r
   break
 for key in ['qwen3_4b','qwen3_2507','qwen35_9b']:
  p=R/('screen-'+key)/'receipt.json'
  if p.exists():assert json.loads(p.read_text())['status']!='failed',str(p)
 time.sleep(10)

def infer(phase,jobs,cap=8192,adapter=None,direct=False,key='qwen3_4b'):
 cmd=[sys.executable,str(D/'infer_batch.py'),'--key',key,'--phase',phase,'--jobs',str(D/jobs),'--cap',str(cap),'--context',str(cap+4096)]
 if adapter:cmd+=['--adapter',adapter]
 if direct:cmd+=['--non-thinking']
 print('Starting '+phase,flush=True);subprocess.run(cmd,check=True)

infer('direct-screen','screen-jobs.json',direct=True,key='qwen35_9b')
infer('confirmation','confirmation-jobs.json')
infer('prompt','confirmation-prompt-jobs.json')
infer('direct','confirmation-jobs.json',direct=True)
infer('long','long-diagnostic-jobs.json',32768)
infer('target-before','target-dev-jobs.json',32768)
print('Starting fixed foundation SFT',flush=True)
run_worker([sys.executable,str(D/'train_foundation.py')],R/'train-foundation.log',1800)
receipt=json.loads((R/'sft-qwen3_4b/receipt.json').read_text());assert receipt['status']=='complete'
adapter=str((R/'sft-qwen3_4b/adapter').resolve())
infer('confirmation-ft','confirmation-jobs.json',adapter=adapter)
infer('target-after','target-dev-jobs.json',32768,adapter=adapter)
print('Bounded FT pilot complete.',flush=True)
