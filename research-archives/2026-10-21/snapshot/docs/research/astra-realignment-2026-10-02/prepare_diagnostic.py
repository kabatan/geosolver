import hashlib,importlib.util,json,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
RUN=ROOT/'qwen/.runtime/astra_realign_20261002'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load(p):return json.loads(Path(p).read_text())
def main():
    RUN.mkdir(exist_ok=False)
    old=ROOT/'qwen/.runtime/geometryzero_input_20261001/jobs.json'
    oldjobs=load(old);base={(j['problem_id'],j['replicate']):j for j in oldjobs if j['arm']=='logic' and j['group']=='main'}
    template_path=ROOT/'docs/research/qwen35-diverse-sft-2026-09-24/english_templates.py'
    spec=importlib.util.spec_from_file_location('numeric_templates',template_path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data=ROOT/'benchmarks/humpty_configurations_v2/training_variants.jsonl'
    rows=[json.loads(l) for l in data.read_text().splitlines()];original={r['id']:r for r in rows if r['variant']=='v0'}
    cases=[]
    for pid,variant in [('H04','v1'),('H04','v2'),('H04','v3'),('H13','v3')]:
        r=next(r for r in rows if (r['id'],r['variant'])==(pid,variant))
        cases.append(dict(case_id=pid+'-'+variant,problem_id=pid,givens=r['givens'],answer_exact=r['answer_exact'],source=str(data),augmentation=r['augmentation']))
    fresh=ROOT/'qwen/.runtime/night_recipe_search_20260929/fresh6-witnesses.researcher-only.json'
    for r in load(fresh):
        if r['source_id']=='DB08':cases.append(dict(case_id=r['id'],problem_id='DB08',givens=r['givens'],answer_exact=r['answer'],source=str(fresh),augmentation='existing-fresh-nonsimilar',witness=r))
    assert len(cases)==6
    jobs=[]
    for c in cases:
        pid=c['problem_id'];old_g=original[pid]['givens'];new_g=c['givens']
        old_en=module.NUMERIC_EN[pid].format(**old_g);new_en=module.NUMERIC_EN[pid].format(**new_g)
        for rep in (1,2):
            b=base[pid,rep];content=b['messages'][0]['content'];assert content.count(old_en)==1
            content=content.replace(old_en,new_en,1)
            prefix,dsl=content.split('Here is the logic form',1)
            changed=[]
            for name,value in new_g.items():
                if name=='cos_ACB':before=f'Equals(CosOf(Angle(A,C,B)),{old_g[name]})';after=f'Equals(CosOf(Angle(A,C,B)),{value})'
                else:before=f'Equals(LengthOf(Line({name[0]},{name[1]})),{old_g[name]})';after=f'Equals(LengthOf(Line({name[0]},{name[1]})),{value})'
                assert dsl.count(before)==1,(c['case_id'],before)
                dsl=dsl.replace(before,after);changed.append(dict(name=name,before=before,after=after))
            content=prefix+'Here is the logic form'+dsl
            j=dict(id=c['case_id']+'-s'+str(rep)+'-main',case_id=c['case_id'],problem_id=pid,group='main',replicate=rep,messages=[dict(role='user',content=content)],seed=b['seed'])
            assert not set(j)&{'answer','answer_exact','target','reference'};jobs.append(j)
            c.setdefault('changes',changed)
    write(RUN/'jobs.json',jobs);write(RUN/'keys.researcher-only.json',cases)
    actor=ROOT/'docs/research/geometryzero-stage1-2026-09-30/rollout-screen-frozen.py'
    write(HERE/'freeze.json',dict(protocol_sha256=sha(HERE/'PROTOCOL.md'),jobs_sha256=sha(RUN/'jobs.json'),keys_sha256=sha(RUN/'keys.researcher-only.json'),prepare_sha256=sha(__file__),actor_sha256=sha(actor),sources={str(p):sha(p) for p in [old,data,fresh,template_path]},groups=12,answers=96))
    print(json.dumps(dict(groups=len(jobs),cases=[c['case_id'] for c in cases])))
if __name__=='__main__':main()
