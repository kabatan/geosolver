"""Deadline-bounded, serial GPU execution of the frozen overnight protocol.

This executes only the specified phase. Branch selection requires an audited
review file; it is not inferred from answer accuracy alone. Every subprocess is
in a new process group, with deadline cleanup limited to that owned group.
"""
import argparse,datetime,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
RUN=ROOT/'qwen/.runtime/night_recipe_search_20260929'
PY=ROOT/'qwen/.runtime/vllm-venv/bin/python'
SHARED=ROOT/'qwen/.runtime/program_self_training_20260926'
GPU=ROOT/'docs/research/program-self-training-2026-09-26/gpu_job.py'
GEN=ROOT/'docs/research/related-numeric-sft-2026-09-28'
TRAIN={32:ROOT/'docs/research/program-self-training-2026-09-26/train_sft.py',128:ROOT/'docs/research/program-self-training-followup-2026-09-26/train_continue.py',512:ROOT/'docs/research/proof-numeric-pilot-2026-09-28/train_fit512.py'}
ARMS={'Base':None,'S128':('S',128),'X128':('X',128),'S512':('S',512),'X512':('X',512),'D512':('D',512),'DX512':('DX',512)}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n');tmp.replace(p)
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def deadline():return datetime.datetime.fromisoformat(read(RUN/'clock.json')['deadline_utc']).timestamp()
def inventory():
    xml=subprocess.check_output(['nvidia-smi','-q','-x'],text=True,timeout=15)
    allowed={
        '/home/kabatan/.local/opt/codex-desktop-linux/codex-app/ChatGPT',
        '/usr/lib/claude-desktop/claude-desktop','/usr/bin/nautilus','/usr/bin/ptyxis',
        '/home/kabatan/.config/discord/app-1.0.159/Discord'}
    rows=[]
    for x in ET.fromstring(xml).findall('.//process_info'):
        if x.findtext('type')!='C+G':continue
        pid=int(x.findtext('pid'));proc=Path('/proc')/str(pid);exe=str((proc/'exe').resolve())
        if exe in allowed:rows.append(dict(pid=pid,executable=exe,cmdline_sha256=sha(proc/'cmdline'),xml_type='C+G'))
    p=RUN/'desktop-inventory.json';write(p,dict(desktop_inventory=rows));return p
def verify_manifest():
    m=read(RUN/'frozen-manifest.json')
    for p,h in m['sha256'].items():assert sha(p)==h,('frozen input changed',p)
def status(**kw):
    row=dict(time=stamp(),**kw);write(RUN/'status.json',row)
    with (RUN/'events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)
def run_gpu(label,cmd,inputs):
    verify_manifest()
    if time.time()>=deadline()-60:raise RuntimeError('Hard deadline too close to start job')
    inv=inventory();log=RUN/'logs'/f'{label}.log';log.parent.mkdir(exist_ok=True)
    guard=[str(PY),str(GPU),'--runtime',str(SHARED),'--label','night20260929-'+label,'--recovery-libs','/usr/lib/x86_64-linux-gnu','--desktop-inventory',str(inv)]
    for p in inputs:guard+=['--input',str(p)]
    guard+=['--']+list(map(str,cmd));start=time.time();status(state='running',job=label,command=cmd,start_unix=start)
    with log.open('x') as out:
        proc=subprocess.Popen(guard,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,cwd=ROOT)
        write(RUN/'active-process.json',dict(pid=proc.pid,pgid=proc.pid,job=label,deadline_unix=deadline(),owned_by='night_recipe_search_20260929'))
        try:rc=proc.wait(timeout=max(1,deadline()-time.time()-15))
        except BaseException as exc:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
            status(state='interrupted',job=label,error=repr(exc),elapsed_seconds=time.time()-start)
            raise
    status(state='job_complete' if rc==0 else 'job_failed',job=label,returncode=rc,elapsed_seconds=time.time()-start)
    write(RUN/'active-process.json',dict(active=False,last_job=label))
    if rc:raise RuntimeError(f'GPU job {label} failed: {rc}; inspect before any one allowed retry')
def train(family,seed=2026093001,target=512):
    for step in [32,128,512]:
        if step>target:break
        label=f'{family}-{seed}-{step}';out=RUN/'train'/label;cfg=RUN/'configs'/f'{label}.json'
        if out.exists():
            r=read(out/'final/receipt.json');assert r['status']=='complete' and r['global_updates']==step
            assert r['config_sha256']==sha(cfg) and r['adapter_sha256']==sha(out/'final/adapter/adapter_model.safetensors')
            continue
        cmd=[str(PY),str(TRAIN[step]),'--config',str(cfg),'--out',str(out)]
        run_gpu('train-'+label,cmd,[cfg,Path(read(cfg)['dataset']),TRAIN[step]])
def adapter(arm,seed=2026093001):
    setting=ARMS.get(arm)
    if arm=='Base':return None
    if setting is None:
        setting={'D6':('D6',512),'DX6':('DX6',512)}[arm]
    family,step=setting
    return RUN/f'train/{family}-{seed}-{step}/final/adapter-vllm'
def generate(arm,kind,jobs,seed=2026093001,cap=32768,context=40960,suffix=''):
    label=f'{arm}-{seed}-{kind}-{cap}{suffix}';out=RUN/'outputs'/label;jobs=Path(jobs)
    if out.exists():
        r=read(out/'receipt.json');assert r['status']=='complete' and r['jobs_sha256']==sha(jobs)
        return out
    driver=GEN/('generate_greedy.py' if kind=='short' else 'generate_batch.py')
    cmd=[str(PY),str(driver),'--jobs',str(jobs),'--out',str(out),'--cap',str(cap),'--context',str(context),'--batch-size','4']
    adapt=adapter(arm,seed)
    inputs=[jobs,driver]
    if adapt:cmd+=['--adapter',str(adapt)];inputs.append(adapt/'adapter_model.safetensors')
    run_gpu('eval-'+label,cmd,inputs);return out
def freeze():
    assert read(RUN/'preparation-receipt.json')['status']=='data_validated'
    assert read(RUN/'fresh6-receipt.json')['status']=='pass'
    for family in ['S','X','D','DX','D6','DX6']:
        assert read(RUN/f'preflight/{family}/receipt.json')['status']=='preflight_complete'
    files=list((RUN/'configs').glob('*.json'))+list((RUN/'data').glob('*.json'))+list((RUN/'jobs').glob('*.json'))+list((RUN/'keys').glob('*.json'))+list(HERE.glob('*.py'))+[HERE/'PROTOCOL.md',RUN/'clock.json',RUN/'construction-witnesses.researcher-only.json',RUN/'independent-validation.json',RUN/'fresh6-witnesses.researcher-only.json']
    files+=list(TRAIN.values())+[GEN/'generate_greedy.py',GEN/'generate_batch.py',GPU]
    files+=[RUN/'fresh6-nonsimilarity-audit.json',RUN/'preparation-receipt.json',RUN/'fresh6-receipt.json']
    assert not (RUN/'frozen-manifest.json').exists()
    write(RUN/'frozen-manifest.json',dict(frozen_utc=stamp(),sha256={str(p):sha(p) for p in files}))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['freeze','initial','train','generate']);ap.add_argument('--family');ap.add_argument('--arm');ap.add_argument('--seed',type=int,default=2026093001);ap.add_argument('--target',type=int,default=512);ap.add_argument('--kind',default='main');ap.add_argument('--jobs');ap.add_argument('--cap',type=int,default=32768);ap.add_argument('--context',type=int,default=40960);ap.add_argument('--suffix',default='');a=ap.parse_args()
    if a.phase=='freeze':freeze();return
    if a.phase=='train':train(a.family,a.seed,a.target);return
    if a.phase=='generate':generate(a.arm,a.kind,a.jobs,a.seed,a.cap,a.context,a.suffix);return
    for family in ['S','X','D','DX']:train(family)
    for arm in ARMS:
        generate(arm,'short',RUN/'jobs/short.json')
        generate(arm,'retention',RUN/'jobs/retention.json')
        generate(arm,'main',RUN/('jobs/main24.json' if arm in ('Base','S128','X128') else 'jobs/main12.json'))
    status(state='initial_phase_complete',next='score, condition-hidden reasoning review, common-cap extensions, then branch gate')
if __name__=='__main__':main()
