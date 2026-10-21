"""Execute this pilot's fixed remaining stages, sequentially, with shared GPU lock."""
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'qwen/.runtime/proof_numeric_pilot_20260928'
SHARED = ROOT / 'qwen/.runtime/program_self_training_20260926'
PYTHON = ROOT / 'qwen/.runtime/vllm-venv/bin/python'
GUARD = ROOT / 'docs/research/program-self-training-2026-09-26/gpu_job.py'
TRAIN = ROOT / 'docs/research/program-self-training-2026-09-26/train_sft.py'
CONTINUE = ROOT / 'docs/research/program-self-training-followup-2026-09-26/train_continue.py'
GENERATE = ROOT / 'docs/research/transfer-reanalysis-2026-09-26/generate_batch.py'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    tmp.replace(path)


def sub(a, b):
    return tuple(x-y for x,y in zip(a,b))


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def cross(a, b):
    return a[0]*b[1]-a[1]*b[0]


def points(sides):
    # Independent primitive coordinate arithmetic, for label audit only.
    # Does not use the target cyclicity or the reference proof.
    a,b,c = sides
    x = (c*c+a*a-b*b)/(2*a)
    A=(x,math.sqrt(c*c-x*x)); B=(0.,0.); C=(float(a),0.)
    midpoint=lambda p,q:tuple((u+v)/2 for u,v in zip(p,q))
    M=midpoint(B,C); N=midpoint(C,A); P=midpoint(A,B)
    w=sub(M,A)
    def bisector_intersection(Q):
        v=sub(Q,A); t=dot(v,v)/(2*dot(v,w))
        assert t>0
        return tuple(u+t*v for u,v in zip(A,w))
    D=bisector_intersection(B); E=bisector_intersection(C)
    w1=sub(D,B); w2=sub(E,C)
    t=cross(sub(C,B),w2)/cross(w1,w2)
    F=tuple(u+t*v for u,v in zip(B,w1))
    bary_c=cross(sub(B,A),sub(F,A))/cross(sub(B,A),sub(C,A))
    bary_b=cross(sub(F,A),sub(C,A))/cross(sub(B,A),sub(C,A))
    assert min(bary_b,bary_c,1-bary_b-bary_c)>0
    return dict(A=A,B=B,C=C,M=M,N=N,P=P,D=D,E=E,F=F)


def prepare():
    receipt=read(OUT/'data/receipt.json')
    train=read(OUT/'data/train-provenance.json')
    key=read(OUT/'data/numeric-private-key.json')
    assert receipt['status']=='complete' and len(train)==256 and len(key)==12
    train_signatures={tuple(r['signature']) for r in train}
    heldout_signatures={tuple(r['signature']) for r in key if r['split']=='heldout'}
    assert len(train_signatures)==64 and len(heldout_signatures)==8
    assert not train_signatures & heldout_signatures
    errors=[]
    for r in train + key[:8]:
        p=points(r['sides_BC_CA_AB']);q=r['query']
        actual=math.dist(p[q[0]],p[q[1]])
        expected=float(r['solver_value'])
        assert abs(actual-expected)<=1e-8*max(1,abs(expected)), r['id']
        assert abs(float(r['target'])-expected)<=5.01e-7
        errors.append(abs(actual-expected))
    public=read(OUT/'data/train.json')
    assert all(set(r)=={'id','source_id','kind','messages','target'} for r in public)
    assert all('concyclic' not in r['messages'][0]['content'] and 'Circumcenter' not in r['messages'][0]['content'] for r in public)
    audit={'status':'pass','checked_solver_labels':len(errors),'max_absolute_error':max(errors),
           'train_shapes':64,'heldout_shapes':8,'overlapping_similarity_signatures':0,
           'teacher_targets':'one rounded decimal only','train_sha256':digest(OUT/'data/train.json')}
    write(OUT/'data-audit.json',audit)
    config=read(ROOT/'docs/research/program-self-training-2026-09-26/config-numeric.json')
    for k in ['selection_receipt','selection_receipt_sha256','generation_length_amendment_sha256']:
        config.pop(k,None)
    config.update(dataset=str(OUT/'data/train.json'),dataset_sha256=digest(OUT/'data/train.json'),
                  seed=2026092801,save_checkpoints=[],protocol_sha256=digest(HERE/'PROTOCOL.md'),
                  data_receipt_sha256=digest(OUT/'data/receipt.json'))
    write(HERE/'config-32.json',config)
    config.update(updates=128,prior_checkpoint=str(OUT/'train32/final'),extension_wrapper_sha256=digest(CONTINUE))
    write(HERE/'config-128.json',config)
    write(OUT/'execution-freeze.json',{'frozen_unix':time.time(),
        'sha256':{str(p):digest(p) for p in [Path(__file__),HERE/'config-32.json',HERE/'config-128.json',OUT/'data/numeric-jobs.json',OUT/'data/train.json']}})


def run(command, label, gpu=False, inputs=()):
    command=[str(x) for x in command]
    if gpu:
        prefix=['python3',str(GUARD),'--runtime',str(SHARED),
                '--label',f'ap01-{label}-20260928','--recovery-libs','/usr/lib/x86_64-linux-gnu',
                '--desktop-inventory',str(OUT/'desktop-inventory.json')]
        for p in inputs: prefix += ['--input',str(p)]
        command=prefix+['--']+command
    print(json.dumps({'stage':label,'status':'starting','unix':time.time()}),flush=True)
    with (OUT/f'{label}-operator.log').open('x') as stream:
        env=os.environ.copy()
        if not gpu:env['CUDA_VISIBLE_DEVICES']=''
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{label} failed ({result.returncode}); see preserved log')
    print(json.dumps({'stage':label,'status':'complete','unix':time.time()}),flush=True)


def generate(arm, kind, jobs, extended=False):
    label=f'{arm}-{kind}'+('-81k' if extended else '')
    command=[PYTHON,GENERATE,'--jobs',jobs,'--out',OUT/label,'--batch-size','4']
    if arm=='sft':command+=['--adapter',OUT/'train128/final/adapter-vllm']
    if extended:command+=['--cap','81920','--context','98304']
    run(command,label,gpu=True,inputs=[jobs,HERE/'PROTOCOL.md'])


def blind():
    review=OUT/'blind';review.mkdir(exist_ok=False)
    private={};proof=[];numeric=[]
    rng=random.Random(2026092899)
    for kind,jobs_path,target in [('proof',OUT/'proof-jobs.json',proof),('numeric',OUT/'data/numeric-jobs.json',numeric)]:
        ext_path=OUT/f'{kind}-extension-jobs.json'
        extended={j['id'] for j in read(ext_path)} if ext_path.exists() else set()
        entries=[(arm,j) for arm in ['base','sft'] for j in read(jobs_path)]
        rng.shuffle(entries)
        for idx,(arm,job) in enumerate(entries):
            cap=81920 if job['id'] in extended else 32768
            source=OUT/(f'{arm}-{kind}'+('-81k' if cap==81920 else ''))/f"{job['id']}-0.json"
            raw=read(source);cid=f'{kind}-{idx:02d}'
            row={'case_id':cid,'messages':raw['messages'],'raw_text':raw['raw_text'],
                 'final_text':raw['final_text'],'finish_reason':raw['finish_reason'],'tokens':len(raw['completion_ids'])}
            write(review/f'{cid}.json',row);target.append({'case_id':cid,'file':str(review/f'{cid}.json'),
                                                          'tokens':row['tokens'],'finish_reason':row['finish_reason']})
            private[cid]={'arm':arm,'job_id':job['id'],'source':str(source),'source_sha256':digest(source),
                          'cap':cap,'split':job['split']}
    write(review/'proof-index.json',proof);write(review/'numeric-index.json',numeric)
    write(OUT/'blind-private-key.json',private)
    write(OUT/'completion.json',{'status':'generated_and_blinded','end_unix':time.time(),
                               'proof_outputs':len(proof),'numeric_outputs':len(numeric)})


def main():
    deadline=time.monotonic()+3600
    while True:
        base=OUT/'base-proof/receipt.json'
        status=read(base).get('status') if base.exists() else None
        if status=='failed':raise RuntimeError('initial base proof generation failed')
        guard_path=SHARED/'ap01-base-proof-20260928/receipt.json'
        guard_status=read(guard_path).get('status') if guard_path.exists() else None
        if guard_status=='failed':raise RuntimeError('initial GPU command failed')
        if status=='complete' and guard_status=='complete' and (OUT/'data/receipt.json').exists():break
        if time.monotonic()>deadline:raise RuntimeError('initial stages did not complete in one hour; inspect')
        time.sleep(5)
    for p,h in read(OUT/'freeze.json')['sha256'].items():assert digest(p)==h,p
    prepare()
    run([PYTHON,TRAIN,'--config',HERE/'config-32.json','--out',OUT/'preflight32','--preflight'],'preflight32')
    run([PYTHON,TRAIN,'--config',HERE/'config-32.json','--out',OUT/'train32'],'train32',gpu=True,inputs=[HERE/'config-32.json',OUT/'data/train.json'])
    run([PYTHON,CONTINUE,'--config',HERE/'config-128.json','--out',OUT/'preflight128','--preflight'],'preflight128')
    run([PYTHON,CONTINUE,'--config',HERE/'config-128.json','--out',OUT/'train128'],'train128',gpu=True,inputs=[HERE/'config-128.json',OUT/'data/train.json'])
    generate('sft','proof',OUT/'proof-jobs.json')
    generate('base','numeric',OUT/'data/numeric-jobs.json')
    generate('sft','numeric',OUT/'data/numeric-jobs.json')
    for kind,jobs_path in [('proof',OUT/'proof-jobs.json'),('numeric',OUT/'data/numeric-jobs.json')]:
        jobs=read(jobs_path);selected=[]
        for job in jobs:
            if any(read(OUT/f'{arm}-{kind}'/f"{job['id']}-0.json")['finish_reason']=='length' for arm in ['base','sft']):
                selected.append(job)
        if selected:
            extension=OUT/f'{kind}-extension-jobs.json';write(extension,selected)
            for arm in ['base','sft']:generate(arm,kind,extension,extended=True)
    blind()


if __name__=='__main__':
    main()
