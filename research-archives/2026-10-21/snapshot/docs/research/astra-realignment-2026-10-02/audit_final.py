import hashlib,json,math
from pathlib import Path
from prepare_diagnostic import HERE,ROOT,RUN,load,sha,write
def main():
    freeze=load(HERE/'freeze.json');receipt=load(RUN/'diagnostic/receipt.json');summary=load(HERE/'summary.json')
    for key,p in [('protocol',HERE/'PROTOCOL.md'),('jobs',RUN/'jobs.json'),('keys',RUN/'keys.researcher-only.json'),('prepare',HERE/'prepare_diagnostic.py')]:assert sha(p)==freeze[key+'_sha256']
    for p,h in freeze['sources'].items():assert sha(p)==h
    actor=ROOT/'docs/research/geometryzero-stage1-2026-09-30/rollout-screen-frozen.py'
    assert sha(actor)==freeze['actor_sha256']==receipt['source_sha256']
    assert receipt['jobs_sha256']==freeze['jobs_sha256'] and receipt['status']=='complete' and receipt['completed_groups']==12
    assert receipt==summary['receipt'] and summary['status']=='complete'
    assert load(HERE/'input-audit.json')['status']=='pass'
    jobs=load(RUN/'jobs.json');scores=load(RUN/'scores.json');raw_index={}
    for j in jobs:
        p=RUN/'diagnostic'/(j['id']+'.json');rr=load(p);assert len(rr)==8
        assert {r['sample'] for r in rr}==set(range(8))
        for r in rr:
            assert r['messages']==j['messages'] and r['seed']==j['seed'] and r['finish_reason']=='stop'
            assert len(r['completion_ids'])==len(r['rollout_logps'])<=1024
            assert all(math.isfinite(x) for x in r['rollout_logps'])
            raw_index[j['id']+'-'+str(r['sample'])]=r
    assert len(scores)==len(raw_index)==96
    assert {r['id'] for r in scores}==set(raw_index)
    for r in scores:
        assert sha(r['source'])==r['source_sha256']
        assert hashlib.sha256(raw_index[r['id']]['raw_text'].encode()).hexdigest()==r['raw_text_sha256']
    for case in summary['cases']:
        rr=[r for r in scores if r['case_id']==case['case_id']]
        assert case['answers']==case['natural']==len(rr)==16
        assert sum(r['relaxed'] for r in rr)==case['correct']
    review=load(HERE/'new-response-review.json');assert review['scores_sha256']==sha(RUN/'scores.json')
    expected={r['id'] for r in scores if r['relaxed']==1 or r['problem_id']=='DB08'}
    assert len(review['reviews'])==34 and {r['id'] for r in review['reviews']}==expected
    for r in review['reviews']:
        assert r['read_full_response'] and sha(r['source'])==r['source_sha256']
        assert hashlib.sha256(raw_index[r['id']]['raw_text'].encode()).hexdigest()==r['raw_text_sha256']
    assert summary['analysis_source_sha256']==sha(HERE/'analyze_diagnostic.py')
    assert summary['score_source_sha256']==sha(ROOT/'docs/research/geometryzero-stage1-2026-09-30/signals.py')
    result=dict(status='pass',groups=12,answers=96,all_naturally_finished=True,reviewed=34,full_mathematical_review_of_all_96=False,
                numerical_relaxed_correct=2,strict_correct=1,new_weight_updates=0,scope='Fixed six-case posthoc initial-signal diagnosis; reviewed all positives and all DB08 responses.',
                model_revision=receipt['revision'],generation_seconds=receipt['elapsed_seconds'],reviewer=review['reviewer'],recommendation_status='Future finite RL proposed; not executed or validated in this turn.')
    write(HERE/'final-audit.json',result)
    files=sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='artifact-manifest.json')
    files+=sorted(p for p in RUN.rglob('*') if p.is_file())
    write(HERE/'artifact-manifest.json',dict(files=[dict(path=str(p),sha256=sha(p)) for p in files]))
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
