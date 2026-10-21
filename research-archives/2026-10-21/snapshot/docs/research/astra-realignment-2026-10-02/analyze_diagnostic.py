import importlib.util,json,math,statistics,sys
from pathlib import Path
from transformers import AutoTokenizer
from prepare_diagnostic import HERE,ROOT,RUN,load,sha,write
def main():
    old=ROOT/'docs/research/geometryzero-stage1-2026-09-30';sys.path.insert(0,str(old))
    spec=importlib.util.spec_from_file_location('fixed_signals',old/'signals.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
    tok=AutoTokenizer.from_pretrained(load(old/'model.json')['snapshot'],local_files_only=True)
    keys={k['case_id']:k for k in load(RUN/'keys.researcher-only.json')};jobs=load(RUN/'jobs.json');receipt=load(RUN/'diagnostic/receipt.json');frozen=load(HERE/'freeze.json')
    assert receipt['status']=='complete' and receipt['completed_groups']==12
    assert receipt['jobs_sha256']==frozen['jobs_sha256'] and receipt['source_sha256']==frozen['actor_sha256']
    scored=[];provenance=[];alltext=[]
    for j in jobs:
        p=RUN/'diagnostic'/(j['id']+'.json');rows=load(p);assert len(rows)==8
        for raw in rows:
            assert raw['messages']==j['messages'] and raw['seed']==j['seed']
            assert len(raw['completion_ids'])==len(raw['rollout_logps'])<=1024
            assert all(math.isfinite(x) for x in raw['rollout_logps'])
            score=s.score(raw,keys[j['case_id']]['answer_exact'],tok)
            score.update(id=j['id']+'-'+str(raw['sample']),case_id=j['case_id'],problem_id=j['problem_id'],replicate=j['replicate'],sample=raw['sample'],source=str(p),source_sha256=sha(p),tokens=len(raw['completion_ids']),raw_text_sha256=__import__('hashlib').sha256(raw['raw_text'].encode()).hexdigest())
            scored.append(score);alltext.append('## '+score['id']+'\n\n'+raw['raw_text']+'\n')
        provenance.append(dict(path=str(p),sha256=sha(p)))
    result=[]
    for cid in keys:
        rr=[r for r in scored if r['case_id']==cid];natural=[r for r in rr if not r['censored']]
        mixed=[]
        for rep in [1,2]:
            ss=[r for r in rr if r['replicate']==rep];mixed.append(all(not r['censored'] for r in ss) and 0<sum(r['relaxed'] or 0 for r in ss)<8)
        result.append(dict(case_id=cid,answers=len(rr),natural=len(natural),correct=sum(r['relaxed'] for r in natural),strict_correct=sum(r['strict'] for r in natural),exact_correct=sum(r['exact'] for r in natural),numeric_mixed=sum(mixed),unparsed=sum(r['parsed'] is None for r in natural),tokens=sum(r['tokens'] for r in rr)))
    write(RUN/'scores.json',scored);write(HERE/'provenance.json',provenance)
    write(HERE/'summary.json',dict(status='complete',answers=96,cases=result,receipt=receipt,score_source_sha256=sha(old/'signals.py'),analysis_source_sha256=sha(__file__),limitations=['Posthoc cause diagnosis, not a new random holdout or training experiment.','Radical DB08 input differs in arithmetic difficulty from integer original.']))
    (HERE/'all-responses.md').write_text('\n'.join(alltext))
    print(json.dumps(dict(cases=result,elapsed_seconds=receipt['elapsed_seconds']),ensure_ascii=False))
if __name__=='__main__':main()
