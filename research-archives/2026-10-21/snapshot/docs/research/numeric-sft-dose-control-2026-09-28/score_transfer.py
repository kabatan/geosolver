"""Score the transfer answer numbers; proofs and derivations require blinded review."""
import math,sys
from pathlib import Path
import run_study as op
sys.path.insert(0,str(op.DOC));import analyze as old_score
P,R,O=op.P,op.R,op.O

def main():
    assert op.read(O/'transfer-generation-complete.json')['status']=='complete'
    jobs=op.read(O/'transfer-jobs.json');key=op.read(O/'transfer-answer-key.json');caps=op.read(O/'transfer-final-cap-by-job.json')
    numeric=[];proof=[]
    for arm in op.ARMS:
        for job in jobs:
            cap=caps.get(job['id'],32768);ref=op.read(O/f'transfer-reference-{arm}-{cap}.json')
            f=Path(ref['directory'])/(job['id']+'-0.json');raw=op.read(f)
            assert op.sha(f)==ref['response_sha256'][job['id']]
            assert raw['messages']==job['messages'] and raw['seed']==job['seed']
            row={'arm':arm,'job_id':job['id'],'source_id':job['source_id'],'split':job['split'],'cap':cap,
                 'file':str(f),'file_sha256':op.sha(f),'finish_reason':raw['finish_reason'],'tokens':len(raw['completion_ids'])}
            if job['split']=='proof':proof.append(row);continue
            expected=float(old_score.parse_numeric(key[job['id']]['answer_exact']));parsed,method,excerpt=old_score.parse(raw['raw_text'])
            value=None
            if parsed is not None:
                try:
                    v=float(old_score.parse_numeric(parsed))
                    if math.isfinite(v):value=v
                except (ValueError,TypeError,OverflowError):pass
            row.update(target=expected,value=value,numeric_correct=None if value is None else abs(value-expected)<=1e-4 or abs(value-expected)/abs(expected)<=1e-5,
                       parse_method=method,answer_excerpt=excerpt[-700:])
            numeric.append(row)
    summary={}
    for arm in op.ARMS:
        summary[arm]={}
        for split in ['untrained_configuration','retention']:
            part=[r for r in numeric if r['arm']==arm and r['split']==split]
            correct=sum(r['numeric_correct'] is True and r['finish_reason']=='stop' for r in part);length=sum(r['finish_reason']=='length' for r in part)
            summary[arm][split]={'n':len(part),'completed_correct':correct,'length':length,'unparsed':sum(r['numeric_correct'] is None for r in part),'bounds':[correct,correct+length]}
        part=[r for r in proof if r['arm']==arm];summary[arm]['proof_generation']={'n':len(part),'length':sum(r['finish_reason']=='length' for r in part)}
    op.write(O/'transfer-scores.json',{'status':'complete','summary':summary,'numeric':numeric,'proof':proof,'note':'Numerical answers only; no mathematical-derivation/proof grades yet.'})
    print(__import__('json').dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
