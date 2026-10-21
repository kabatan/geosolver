import hashlib,json,runpy,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUN=ROOT/'qwen/.runtime/numeric_rl_feasibility_20260930'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def main():
    RUN.mkdir(exist_ok=False)
    data=ROOT/'qwen/.runtime/night_recipe_search_20260929/data/holdout.json'
    rows=json.loads(data.read_text());families=['H01','H04','H07','H13','H15','DA01','DA05']
    templates=ROOT/'docs/research/qwen35-diverse-sft-2026-09-24/english_templates.py'
    en=runpy.run_path(str(templates))['NUMERIC_EN']
    dev=ROOT/'qwen/configs/exp03_numeric_dev12.jsonl'
    simple={r['id']:r for r in map(json.loads,dev.read_text().splitlines())}
    intro='Solve the numerical geometry problem below. Give a concise, coherent derivation; any correct method is allowed. End with a single line Answer: <value>, using an exact expression or at least 8 significant digits.\n\n'
    jobs=[];keys={}
    for cid in families:
        r=next(x for x in rows if x['source_id']==cid)
        problem=r['messages'][0]['content'].split('\n\n',1)[1]
        ident='continuous-'+cid
        jobs.append(dict(id=ident,source_id=cid,stratum='continuous',source_row_id=r['id'],messages=[dict(role='user',content=intro+problem)],seed=2026093040+len(jobs)))
        keys[ident]=dict(answer=r['target'],source_file=str(data),source_row_id=r['id'],oracle='original point/line/circle construction; independent 60-digit validation already recorded')
    for cid in ['H01','H04','DA01','DA07','DA15']:
        r=simple[cid];ident='simple-'+cid
        problem=en[cid].format(**r['givens'])
        jobs.append(dict(id=ident,source_id=cid,stratum='simple',source_row_id=cid+'-'+r['variant'],messages=[dict(role='user',content=intro+problem)],seed=2026093040+len(jobs)))
        keys[ident]=dict(answer=r['answer_exact'],source_file=str(dev),source_row_id=cid+'-'+r['variant'],oracle='previous verified exp03 numeric dev; literal English template of original givens')
    write(RUN/'jobs.json',jobs);write(RUN/'keys.researcher-only.json',keys)
    meta=ROOT/'docs/research/qwen35-self-materials-2026-09-23/model.json'
    frozen=[HERE/'PROTOCOL.md',Path(__file__),data,dev,templates,meta,RUN/'jobs.json',RUN/'keys.researcher-only.json']
    write(RUN/'freeze.json',dict(created_unix=time.time(),scope='feasibility only; no transfer claims',jobs=len(jobs),samples=4,sampling=dict(temperature=1,top_p=1,top_k=-1,presence_penalty=0),tolerance=dict(abs=1e-4,rel=1e-5),sha256={str(p):sha(p) for p in frozen}))
    print(json.dumps(dict(status='prepared',jobs=len(jobs),source_families=sorted({j['source_id'] for j in jobs}))))
if __name__=='__main__':main()
