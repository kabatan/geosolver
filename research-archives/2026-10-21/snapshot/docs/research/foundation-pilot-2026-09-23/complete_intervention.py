"""Resume after a diagnosed FP32-to-BF16 adapter reload check failure."""
import json,subprocess,sys
from pathlib import Path
from qwen.grpo_run import run_worker
D=Path(__file__).resolve().parent;R=Path('qwen/.runtime/foundation_pilot_20260923')
out=R/'sft-qwen3_4b-replay'
run_worker([sys.executable,str(D/'train_foundation.py'),'--out',str(out)],R/'train-foundation-replay.log',1800)
rec=json.loads((out/'receipt.json').read_text());assert rec['status']=='complete'
for phase,jobs,cap in [('confirmation-ft','confirmation-jobs.json',8192),('target-after','target-dev-jobs.json',32768)]:
 cmd=[sys.executable,str(D/'infer_batch.py'),'--key','qwen3_4b','--phase',phase,'--jobs',str(D/jobs),'--cap',str(cap),'--context',str(cap+4096),'--adapter',str((out/'adapter').resolve())]
 print('Starting '+phase,flush=True);subprocess.run(cmd,check=True)
print('Bounded FT pilot complete after technical replay.',flush=True)
