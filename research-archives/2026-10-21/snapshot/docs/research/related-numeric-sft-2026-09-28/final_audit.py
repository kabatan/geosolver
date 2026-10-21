"""Verify completed primary evaluation and supplementary receipts before reporting."""
import collections, hashlib, json, time
from pathlib import Path

P = Path(__file__).resolve().parent
R = P.parents[2]
O = R/'qwen/.runtime/related_numeric_sft_20260928'
ARMS = ['base','sft-a','sft-b']
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    checks = []
    for freeze in ['main-freeze.json','data-freeze.json','greedy-freeze.json']:
        for file, digest in read(O/freeze)['sha256'].items():
            assert sha(Path(file)) == digest, file
        checks.append(f'{freeze}: every frozen hash matches')
    for done in ['generation-complete.json','automatic-diagnostics-complete.json','automatic-greedy-complete.json']:
        assert read(O/done)['status']=='complete', done
    scores = read(O/'numeric-scores.json')
    caps = read(O/'final-cap-by-job.json')
    jobs = {j['id']:j for kind in ['main','diagnostic'] for j in read(O/f'{kind}-jobs.json')}
    assert len(jobs)==44 and len(scores['numeric'])==120 and len(scores['proof'])==12
    for arm in ARMS:
        rows = [r for r in scores['numeric']+scores['proof'] if r['arm']==arm]
        assert {r['job_id'] for r in rows}==set(jobs)
        for row in rows:
            file = Path(row['file']); raw=read(file); receipt=read(file.parent/'receipt.json'); job=jobs[row['job_id']]
            assert receipt['status']=='complete'
            assert sha(file)==row['file_sha256']
            assert receipt['cap']==row['cap']==caps.get(row['job_id'],32768)
            assert raw['messages']==job['messages'] and raw['seed']==job['seed']
            assert raw['revision']==receipt['model_revision']=='c202236235762e1c871ad0ccb60c8ee5ba337b9a'
            assert receipt['driver_sha256']==sha(P/'generate_batch.py')
            for k,v in {'temperature':.7,'top_p':.95,'top_k':20,'presence_penalty':.2,'enable_thinking':False,'batch_size':4}.items():
                assert receipt[k]==v,(arm,k)
            adapter=None if arm=='base' else O/f'{arm}-train128/final/adapter-vllm'
            assert raw['adapter']==(str(adapter) if adapter else None)
            assert receipt['adapter_sha256']==(sha(adapter/'adapter_model.safetensors') if adapter else None)
        checks.append(f'{arm}: 44 primary outputs, messages/seeds/budget/model/adapter/decoding match')
    for kind in ['main','diagnostic']:
        for old_cap,new_cap in [(32768,81920),(81920,131072)]:
            suffix='' if old_cap==32768 else '-'+str(old_cap)
            previous=read(O/f'{kind}-jobs.json') if old_cap==32768 else (read(O/f'{kind}-extension-{old_cap}-jobs.json') if (O/f'{kind}-extension-{old_cap}-jobs.json').exists() else [])
            needed={j['id'] for j in previous if any(read(O/f'{a}-{kind}{suffix}'/(j['id']+'-0.json'))['finish_reason']=='length' for a in ARMS)}
            extension=O/f'{kind}-extension-{new_cap}-jobs.json'
            actual={j['id'] for j in read(extension)} if extension.exists() else set()
            assert needed==actual,(kind,old_cap,needed,actual)
    checks.append('Adaptive extensions exactly equal the union of prior length-finished jobs')
    bank=read(O/'review-bank.json')
    assert not bank['final_missing'], bank['final_missing']
    proof_summary={}; derivation_summary={}
    numeric_by_job={(r['arm'],r['job_id']):r for r in scores['numeric']}
    for arm in ARMS:
        proof=[x for x in bank['final_required'] if x['arm']==arm and x['review']['kind']=='proof']
        numeric=[x for x in bank['final_required'] if x['arm']==arm and x['review']['kind']=='numeric']
        assert len(proof)==4
        proof_summary[arm]={'n':4,'complete':sum(x['review']['grade']['complete_proof'] for x in proof),'scores':[x['review']['grade']['score'] for x in proof]}
        derivation_summary[arm]={'reviewed':len(numeric),'correct_with_valid_derivation':sum(x['finish_reason']=='stop' and numeric_by_job[(arm,x['job_id'])]['numeric_correct'] is True and x['review']['grade'].get('derivation_status')=='valid' for x in numeric)}
    checks.append('All final proofs and all correct/unparsed main numerical answers have content-matched reviews')
    greedy=read(O/'greedy-fit-scores.json')
    assert greedy['status']=='complete' and len(greedy['rows'])==180
    for arm in ['base','sft-a']:
        receipt=read(O/f'{arm}-greedy-fit/receipt.json')
        assert receipt['status']=='complete' and receipt['completed_jobs']==90
        for key,value in {'temperature':0.,'presence_penalty':0.,'top_p':1.,'top_k':-1}.items(): assert receipt[key]==value
    decision=read(O/'digit-probe-decision.json')
    if decision['run_probe']:
        for arm in ['base','sft-a']:
            assert read(O/f'{arm}-digit-probe/run.json')['status']=='complete'
            assert len((O/f'{arm}-digit-probe/token-losses.jsonl').read_text().splitlines())==90
    report={'status':'complete','unix':time.time(),'checks':checks,'proof_summary':proof_summary,'numeric_derivation_summary':derivation_summary,
            'limitations':['Exploratory known benchmark, eight unseen SFT construction IDs, one proof problem with four decoding samples.',
                           'Two SFT seeds; no shuffled-label training control.',
                           'Diagnostic prompt amended before its first response; greedy/loss/constant-baseline analyses are supplementary, not primary endpoints.']}
    (O/'final-integrity-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
