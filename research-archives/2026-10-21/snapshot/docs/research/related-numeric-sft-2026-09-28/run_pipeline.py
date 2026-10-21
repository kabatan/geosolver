"""Sequential, resumable GPU operator. No concurrent model workers."""
from pathlib import Path
import hashlib,json,os,subprocess,time
P=Path(__file__).resolve().parent;R=P.parents[2];O=R/'qwen/.runtime/related_numeric_sft_20260928'
SH=R/'qwen/.runtime/program_self_training_20260926';PY=R/'qwen/.runtime/vllm-venv/bin/python'
GUARD=R/'docs/research/program-self-training-2026-09-26/gpu_job.py'
TRAIN=GUARD.parent/'train_sft.py';CONT=R/'docs/research/program-self-training-followup-2026-09-26/train_continue.py'
ARMS=['base','sft-a','sft-b']
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');t.replace(p)
def status(stage,state):
 row={'stage':stage,'status':state,'unix':time.time()}
 with (O/'operator-events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 print(json.dumps(row),flush=True)
def run(args,label,gpu=False,inputs=()):
 args=list(map(str,args));receipt=O/label/'receipt.json'
 if receipt.exists():
  if read(receipt)['status'] in ('complete','preflight_complete'):return
  raise RuntimeError('Existing incomplete stage '+label)
 if gpu:
  prefix=['python3',str(GUARD),'--runtime',str(SH),'--label','related-numeric-'+label+'-20260928','--recovery-libs','/usr/lib/x86_64-linux-gnu','--desktop-inventory',str(O/'desktop-inventory.json')]
  for f in inputs:prefix+=['--input',str(f)]
  args=prefix+['--']+args
 status(label,'starting')
 with (O/(label+'-operator.log')).open('x') as log:
  env=os.environ.copy()
  if not gpu:env['CUDA_VISIBLE_DEVICES']=''
  p=subprocess.run(args,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT)
 if p.returncode:raise RuntimeError(f'Stage {label} exited {p.returncode}')
 status(label,'complete')
def generate(arm,kind,jobs,cap=32768,context=40960):
 label=f'{arm}-{kind}'+(f'-{cap}' if cap!=32768 else '')
 args=[PY,P/'generate_batch.py','--jobs',jobs,'--out',O/label,'--batch-size','4','--cap',cap,'--context',context]
 if arm!='base':args+=['--adapter',O/f'{arm}-train128/final/adapter-vllm']
 run(args,label,True,[jobs,P/'PROTOCOL.md'])
def main():
 for freeze in ['main-freeze.json','data-freeze.json']:
  for f,h in read(O/freeze)['sha256'].items():assert sha(Path(f))==h,f
 # Base main has already been launched while constructing datasets.
 while True:
  p=SH/'related-numeric-base-main-20260928/receipt.json'
  if p.exists():
   s=read(p)['status']
   if s=='complete':break
   if s=='failed':raise RuntimeError('Baseline main worker failed')
  time.sleep(5)
 for arm in ARMS[1:]:
  for updates,script in [(32,TRAIN),(128,CONT)]:
   conf=P/f'config-{arm}-{updates}.json';label=f'{arm}-train{updates}'
   run([PY,script,'--config',conf,'--out',O/(label+'-preflight'),'--preflight'],label+'-preflight')
   run([PY,script,'--config',conf,'--out',O/label],label,True,[conf,O/'train.json'])
 for arm in ARMS[1:]:generate(arm,'main',O/'main-jobs.json')
 status('main-initial-all-arms','complete')
 for arm in ARMS:generate(arm,'diagnostic',O/'diagnostic-jobs.json')
 chosen={}
 for kind in ['main','diagnostic']:
  jobs=read(O/f'{kind}-jobs.json');remaining=jobs
  for current,nextcap,nextcontext in [(32768,81920,98304),(81920,131072,147456)]:
   suffix='' if current==32768 else f'-{current}'
   selected=[j for j in remaining if any(read(O/f'{a}-{kind}{suffix}'/(j['id']+'-0.json'))['finish_reason']=='length' for a in ARMS)]
   if not selected:break
   p=O/f'{kind}-extension-{nextcap}-jobs.json';write(p,selected)
   for a in ARMS:generate(a,kind,p,nextcap,nextcontext)
   for j in selected:chosen[j['id']]=nextcap
   remaining=selected
 write(O/'final-cap-by-job.json',chosen)
 write(O/'generation-complete.json',{'status':'complete','unix':time.time(),'arms':ARMS,'jobs_per_arm':44,'chosen_caps':chosen})
 status('all-generation','complete')
if __name__=='__main__':main()
