"""Verify frozen inputs, saved rollout integrity, and complete review coverage."""
import hashlib,json,math
from collections import Counter
from pathlib import Path
from formalize import HERE,ROOT,RUN,OLD,sha,write

def read(p):return json.loads(Path(p).read_text())

def main():
    frozen=read(HERE/'freeze.json');summary=read(HERE/'summary.json')
    check_paths={'jobs':RUN/'jobs.json','formalizer':HERE/'formalize.py',
                 'protocol':HERE/'PROTOCOL-frozen.md','old_jobs':OLD/'jobs.json',
                 'old_selection':ROOT/'docs/research/geometryzero-stage1-2026-09-30/selection.json'}
    for key,p in check_paths.items():assert sha(p)==frozen[key],(key,str(p))
    receipt=read(RUN/'screen1024-v2/receipt.json');old_receipt=read(OLD/'screen1024/receipt.json')
    assert receipt==summary['new_actor_receipt'] and receipt['status']=='complete'
    assert receipt['jobs_sha256']==frozen['jobs'] and receipt['completed_groups']==216
    actor=ROOT/'docs/research/geometryzero-stage1-2026-09-30/rollout-screen-frozen.py'
    assert sha(actor)==receipt['source_sha256']
    for k in ['model','revision','cap','samples','temperature','top_p','top_k']:
        assert receipt[k]==old_receipt[k],k
    input_audit=read(HERE/'input-audit.json')
    assert input_audit['status']=='pass' and input_audit['actor_jobs_sha256']==frozen['jobs']
    assert input_audit['source_sha256']==frozen['formalizer']
    assert input_audit['audit_source_sha256']==sha(HERE/'audit_inputs.py')
    assert len(input_audit['lens'])==216 and input_audit['max_prompt_tokens']<=2048
    jobs=read(RUN/'jobs.json');old_jobs={(j['problem_id'],j['group']):j for j in read(OLD/'jobs.json')}
    assert len(jobs)==216 and len({j['id'] for j in jobs})==216
    givens={pid:j['messages'][0]['content'].split('Geometry specification and question:\n',1)[1].split('\nOutput the thinking process',1)[0] for (pid,g),j in old_jobs.items()}
    for j in jobs:
        old=old_jobs[j['problem_id'],j['group']]
        assert j['seed']==old['seed']+(1000000 if j['replicate']==2 else 0)
        if j['arm']=='text':assert j['messages']==old['messages'] and j['replicate']==2
        else:assert givens[j['problem_id']] in j['messages'][0]['content']
    new_index={j['id']:j for j in jobs};raw_index={};tokens=Counter();finish=Counter()
    provenance=read(HERE/'provenance.json');assert len(provenance)==288
    for entry in provenance:
        p=Path(entry['path']);assert sha(p)==entry['sha256']
        rows=read(p);assert len(rows)==8 and {r['sample'] for r in rows}==set(range(8))
        for r in rows:
            key=f'{entry["problem_id"]}-{entry["arm"]}-s{entry["replicate"]}-{entry["group"]}-{r["sample"]}'
            assert key not in raw_index;raw_index[key]=r
            assert r['cap']==1024 and len(r['completion_ids'])<=1024
            assert len(r['completion_ids'])==len(r['rollout_logps'])
            assert all(math.isfinite(x) for x in r['rollout_logps'])
            tokens[entry['arm']]+=len(r['completion_ids']);finish[entry['arm']+':'+r['finish_reason']]+=1
            old=old_jobs[entry['problem_id'],entry['group']]
            if (entry['arm'],entry['replicate'])==('text',1):
                assert r['messages']==old['messages'] and r['seed']==old['seed']
            else:
                j=new_index[r['id']];assert r['messages']==j['messages'] and r['seed']==j['seed']
                assert len(r['prompt_ids'])==input_audit['lens'][j['id']]
    assert len(raw_index)==2304
    scores=read(RUN/'scores.json');assert len(scores)==2304
    assert {r['id'] for r in scores}==set(raw_index)
    for r in scores:
        raw=raw_index[r['id']]
        assert r['tokens']==len(raw['completion_ids'])
        assert sha(r['source'])==r['source_sha256']
    for arm in ('text','logic'):
        for group in ('main','with','without'):
            rows=[r for r in scores if r['arm']==arm and r['group']==group]
            out=summary['arms'][arm][group]
            assert len(rows)==384 and out['answers']==384
            assert out['natural']==sum(not r['censored'] for r in rows)
            assert out['correct']==sum(r['relaxed'] or 0 for r in rows)
            assert out['tokens']==sum(r['tokens'] for r in rows)
    review=read(HERE/'quality-review.json');positive={r['id'] for r in scores if r['group']=='main' and r['relaxed']==1}
    assert len(review['reviews'])==72 and {r['id'] for r in review['reviews']}==positive
    for r in review['reviews']:
        assert sha(r['source'])==r['source_sha256']
        assert hashlib.sha256(raw_index[r['id']]['raw_text'].encode()).hexdigest()==r['raw_text_sha256']
    prior=ROOT/'docs/research/geometryzero-stage1-2026-09-30/QUALITY_REVIEW.md'
    assert sha(prior)==review['prior_review_sha256']
    assert summary['score_source_sha256']==sha(ROOT/'docs/research/geometryzero-stage1-2026-09-30/signals.py')
    assert summary['comparison_source_sha256']==sha(HERE/'analyze.py')
    results={'status':'pass','frozen_hashes_verified':list(check_paths),'new_groups':216,'total_groups':288,'total_answers':2304,'new_answers':1728,
             'model_revision':receipt['revision'],'completion_tokens':dict(tokens),'finish_reasons':dict(finish),
             'reviewed_numeric_positive_main':len(positive),'review_scope':review['scope'],'reviewer':review['reviewer'],
             'no_weight_updates_in_comparison':True,'elapsed_generation_seconds':receipt['elapsed_seconds'],
             'limitations':input_audit['limitations']+['Existing fixed scores checked for coverage and consistency; scoring implementation SHA verified.','Review judgments are not independent formal proof certificates.']}
    write(HERE/'final-audit.json',results)
    paths=sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='artifact-manifest.json')
    paths+=sorted(p for p in RUN.iterdir() if p.is_file())+[RUN/'screen1024-v2/receipt.json']
    write(HERE/'artifact-manifest.json',{'files':[{'path':str(p),'sha256':sha(p)} for p in paths],
          'raw_group_files':provenance,'note':'Manifest excludes itself; raw groups include immutable reused text seed1.'})
    print(json.dumps(results,ensure_ascii=False))

if __name__=='__main__':main()
