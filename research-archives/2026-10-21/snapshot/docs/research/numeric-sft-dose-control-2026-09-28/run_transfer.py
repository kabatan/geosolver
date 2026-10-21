"""Exploratory transfer evaluation; reuse prior outputs only on exact run identity."""
import json,subprocess,time
from pathlib import Path
import run_study as op
P,R,O=op.P,op.R,op.O
DRIVER=op.DOC/'generate_batch.py'
OLD_ARMS={'base':'base','correct128':'sft-a'}

def stage(arm,jobs_path,cap,context):
    jobs=op.read(jobs_path);suffix='' if cap==32768 else '-'+str(cap)
    reuse=None
    if arm in OLD_ARMS:
        old=op.OLD/f'{OLD_ARMS[arm]}-main{suffix}';rf=old/'receipt.json'
        if rf.exists():
            receipt=op.read(rf)
            identity={'status':'complete','jobs_sha256':op.sha(jobs_path),'driver_sha256':op.sha(DRIVER),
                      'cap':cap,'context':context,'batch_size':4,'temperature':.7,'top_p':.95,'top_k':20,
                      'presence_penalty':.2,'enable_thinking':False,'completed_jobs':len(jobs),
                      'adapter_sha256':op.sha(op.ADAPTERS[arm]/'adapter_model.safetensors') if op.ADAPTERS[arm] else None}
            if all(receipt.get(k)==v for k,v in identity.items()):
                for i,j in enumerate(jobs):
                    raw=op.read(old/(j['id']+'-0.json'))
                    assert raw['messages']==j['messages'] and raw['seed']==j['seed'] and raw['batch_start']==(i//4)*4
                    assert raw['revision']=='c202236235762e1c871ad0ccb60c8ee5ba337b9a'
                reuse=old
    if reuse:
        destination=reuse;origin='reused prior exact-identity run'
        op.status(f'{arm}-transfer{suffix}','reused')
    else:
        label=f'{arm}-transfer{suffix}';destination=O/label;origin='generated in this study'
        args=[op.PY,DRIVER,'--jobs',jobs_path,'--out',destination,'--cap',cap,'--context',context,'--batch-size','4']
        if op.ADAPTERS[arm]:args+=['--adapter',op.ADAPTERS[arm]]
        op.run(args,label,True,[jobs_path,DRIVER,P/'TRANSFER_EXTENSION.md'])
    op.write(O/f'transfer-reference-{arm}-{cap}.json',{'arm':arm,'cap':cap,'context':context,'origin':origin,
             'directory':str(destination),'receipt_sha256':op.sha(destination/'receipt.json'),
             'jobs_sha256':op.sha(jobs_path),'response_sha256':{j['id']:op.sha(destination/(j['id']+'-0.json')) for j in jobs}})
    return destination

def main():
    assert op.read(O/'fit-scores.json')['status']=='complete'
    for path,digest in op.read(O/'transfer-freeze.json')['sha256'].items():assert op.sha(Path(path))==digest,path
    jobs_path=O/'transfer-jobs.json';jobs=op.read(jobs_path);current={}
    for arm in op.ARMS:current[arm]=stage(arm,jobs_path,32768,40960)
    chosen={};remaining=jobs
    for old,cap,context in [(32768,81920,98304),(81920,131072,147456)]:
        selected=[j for j in remaining if any(op.read(current[a]/(j['id']+'-0.json'))['finish_reason']=='length' for a in op.ARMS)]
        if not selected:break
        path=O/f'transfer-extension-{cap}-jobs.json';op.write(path,selected)
        for arm in op.ARMS:current[arm]=stage(arm,path,cap,context)
        chosen.update({j['id']:cap for j in selected});remaining=selected
    op.write(O/'transfer-final-cap-by-job.json',chosen)
    op.write(O/'transfer-generation-complete.json',{'status':'complete','unix':time.time(),'jobs_per_arm':24,'chosen_caps':chosen})
    subprocess.run([str(op.CPU),str(P/'score_transfer.py')],cwd=R,check=True)
    op.status('exploratory-transfer','complete')
if __name__=='__main__':main()
