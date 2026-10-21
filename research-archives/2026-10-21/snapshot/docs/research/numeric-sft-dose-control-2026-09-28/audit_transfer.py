"""Verify completed exploratory transfer and exact-identity reuse receipts."""
from pathlib import Path
import json,time
import run_study as op
P,R,O=op.P,op.R,op.O
DRIVER=op.DOC/'generate_batch.py'

def main():
    checks=[]
    freeze=op.read(O/'transfer-freeze.json')
    for file,digest in freeze['sha256'].items():assert op.sha(Path(file))==digest,file
    assert op.read(O/'transfer-generation-complete.json')['status']=='complete'
    jobs=op.read(O/'transfer-jobs.json');caps=op.read(O/'transfer-final-cap-by-job.json');scores=op.read(O/'transfer-scores.json')
    assert len(jobs)==24 and len(scores['numeric'])==80 and len(scores['proof'])==16
    refs={};reused=[]
    for cap,context in [(32768,40960),(81920,98304),(131072,147456)]:
        jobs_file=O/('transfer-jobs.json' if cap==32768 else f'transfer-extension-{cap}-jobs.json')
        if not jobs_file.exists():continue
        these_jobs=op.read(jobs_file)
        for arm in op.ARMS:
            ref=op.read(O/f'transfer-reference-{arm}-{cap}.json');directory=Path(ref['directory']);receipt=op.read(directory/'receipt.json')
            refs[(arm,cap)]=ref
            assert receipt['status']=='complete' and op.sha(directory/'receipt.json')==ref['receipt_sha256']
            assert receipt['jobs_sha256']==ref['jobs_sha256']==op.sha(jobs_file)
            assert set(ref['response_sha256'])=={j['id'] for j in these_jobs}
            adapter=op.ADAPTERS[arm]
            assert receipt['adapter']==(str(adapter) if adapter else None)
            assert receipt['adapter_sha256']==(op.sha(adapter/'adapter_model.safetensors') if adapter else None)
            assert receipt['driver_sha256']==op.sha(DRIVER)
            identity={'cap':cap,'context':context,'temperature':.7,'top_p':.95,'top_k':20,'presence_penalty':.2,'enable_thinking':False,'batch_size':4,'completed_jobs':len(these_jobs),'samples':1}
            for k,v in identity.items():assert receipt[k]==v,(arm,cap,k)
            for i,job in enumerate(these_jobs):
                f=directory/(job['id']+'-0.json');raw=op.read(f)
                assert op.sha(f)==ref['response_sha256'][job['id']]
                assert raw['messages']==job['messages'] and raw['seed']==job['seed'] and raw['batch_start']==(i//4)*4
                assert raw['revision']==receipt['model_revision']=='c202236235762e1c871ad0ccb60c8ee5ba337b9a'
                assert raw['adapter']==receipt['adapter']
            if ref['origin'].startswith('reused'):reused.append({'arm':arm,'cap':cap,'jobs':len(these_jobs),'directory':str(directory)})
    previous=jobs
    for old,new in [(32768,81920),(81920,131072)]:
        needed={j['id'] for j in previous if any(op.read(Path(refs[(a,old)]['directory'])/(j['id']+'-0.json'))['finish_reason']=='length' for a in op.ARMS)}
        f=O/f'transfer-extension-{new}-jobs.json';these=op.read(f) if f.exists() else []
        assert needed=={j['id'] for j in these},(old,needed,these)
        previous=these
    checks.append('Every cap/batch/source/model/adapter/sampling identity and reused receipt/response hash matches')
    checks.append('Extensions exactly equal the union of all four arms’ length-finished jobs')
    by_job={j['id']:j for j in jobs}
    for arm in op.ARMS:
        rows=[r for r in scores['numeric']+scores['proof'] if r['arm']==arm]
        assert {r['job_id'] for r in rows}==set(by_job)
        for row in rows:
            assert row['cap']==caps.get(row['job_id'],32768)
            assert row['file_sha256']==op.sha(Path(row['file']))
            assert row['file']==str(Path(refs[(arm,row['cap'])]['directory'])/(row['job_id']+'-0.json'))
    checks.append('Final scores use every one of 24 jobs per arm at the final common cap')
    result={'status':'complete','unix':time.time(),'checks':checks,'reused_stages':reused,'transfer_scores_sha256':op.sha(O/'transfer-scores.json'),
            'classification':freeze['classification'],'note':'Proof and derivation grades are audited separately through content-matched review collection.'}
    op.write(O/'transfer-integrity-audit.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
