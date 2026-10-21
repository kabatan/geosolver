"""Frozen, serial dose/control study using unchanged, verified GPU drivers."""
from pathlib import Path
import hashlib, json, os, subprocess, time

P=Path(__file__).resolve().parent
R=P.parents[2]
O=R/'qwen/.runtime/numeric_sft_dose_control_20260928'
OLD=R/'qwen/.runtime/related_numeric_sft_20260928'
DOC=R/'docs/research/related-numeric-sft-2026-09-28'
PY=R/'qwen/.runtime/vllm-venv/bin/python'
CPU=R/'.venv/bin/python'
SH=R/'qwen/.runtime/program_self_training_20260926'
GUARD=R/'docs/research/program-self-training-2026-09-26/gpu_job.py'
TRAIN=GUARD.parent/'train_sft.py'
CONT=R/'docs/research/program-self-training-followup-2026-09-26/train_continue.py'
FIT=R/'docs/research/proof-numeric-pilot-2026-09-28/train_fit512.py'
DRIVER=DOC/'generate_greedy.py'
ARMS=['base','correct128','correct512','shuffled512']
ADAPTERS={'base':None,'correct128':OLD/'sft-a-train128/final/adapter-vllm',
          'correct512':O/'correct-train512/final/adapter-vllm',
          'shuffled512':O/'shuffled-train512/final/adapter-vllm'}

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
def status(stage,state):
    row={'stage':stage,'status':state,'unix':time.time()}
    with (O/'operator-events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)
def run(args,label,gpu=False,inputs=()):
    receipt=O/label/'receipt.json'
    if receipt.exists():
        if read(receipt)['status'] in ('complete','preflight_complete'):return
        raise RuntimeError('Existing incomplete stage '+label)
    args=list(map(str,args))
    if gpu:
        prefix=['python3',str(GUARD),'--runtime',str(SH),'--label','dose-control-'+label+'-20260928',
                '--recovery-libs','/usr/lib/x86_64-linux-gnu','--desktop-inventory',str(O/'desktop-inventory.json')]
        for f in inputs:prefix+=['--input',str(f)]
        args=prefix+['--']+args
    status(label,'starting')
    env=os.environ.copy()
    if not gpu:env['CUDA_VISIBLE_DEVICES']=''
    with (O/(label+'-operator.log')).open('x') as log:
        result=subprocess.run(args,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'{label}: returncode {result.returncode}')
    status(label,'complete')
def generate(arm,jobs,cap=32768,context=40960):
    label=f'{arm}-fit'+('' if cap==32768 else '-'+str(cap))
    args=[PY,DRIVER,'--jobs',jobs,'--out',O/label,'--cap',cap,'--context',context,'--batch-size','4']
    if ADAPTERS[arm]:args+=['--adapter',ADAPTERS[arm]]
    run(args,label,True,[jobs,P/'PROTOCOL.md',DRIVER])
def main():
    for path,digest in read(O/'freeze.json')['sha256'].items():assert sha(Path(path))==digest,path
    # Complete all CPU validation before starting a model worker. Resume wrappers
    # require their prior checkpoint, so their preflights run at that point.
    stages=[('correct',512,FIT),('shuffled',32,TRAIN),('shuffled',128,CONT),('shuffled',512,FIT)]
    for arm,updates,script in stages:
        c=P/f'config-{arm}-{updates}.json';label=f'{arm}-train{updates}'
        run([PY,script,'--config',c,'--out',O/(label+'-preflight'),'--preflight'],label+'-preflight')
        run([PY,script,'--config',c,'--out',O/label],label,True,[c,Path(read(c)['dataset']),P/'PROTOCOL.md',script])
    for arm in ARMS:generate(arm,O/'fit-jobs.json')
    chosen={};remaining=read(O/'fit-jobs.json')
    for old_cap,cap,context in [(32768,81920,98304),(81920,131072,147456)]:
        suffix='' if old_cap==32768 else '-'+str(old_cap)
        selected=[j for j in remaining if any(read(O/f'{a}-fit{suffix}'/(j['id']+'-0.json'))['finish_reason']=='length' for a in ARMS)]
        if not selected:break
        jobs=O/f'fit-extension-{cap}-jobs.json';write(jobs,selected)
        for arm in ARMS:generate(arm,jobs,cap,context)
        chosen.update({j['id']:cap for j in selected});remaining=selected
    write(O/'final-cap-by-job.json',chosen)
    write(O/'fit-generation-complete.json',{'status':'complete','unix':time.time(),'arms':ARMS,'jobs_per_arm':110,'chosen_caps':chosen})
    subprocess.run([str(CPU),str(P/'score_fit.py')],cwd=R,check=True)
    status('short-answer-study','complete')
if __name__=='__main__':main()
