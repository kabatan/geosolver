"""Prepare a partial scoring snapshot solely for concurrent, content-keyed review."""
import argparse,math,sys
from pathlib import Path
import run_study as op
sys.path.insert(0,str(op.DOC));import analyze as sc

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);ap.add_argument('--arms',nargs='+',choices=op.ARMS,required=True)
    ap.add_argument('--cap',type=int,default=32768);ap.add_argument('--exclude-jobs',nargs='*',default=[]);args=ap.parse_args()
    out=op.O/f'transfer-snapshot-{args.label}.json';assert not out.exists()
    jobs=op.read(op.O/'transfer-jobs.json');key=op.read(op.O/'transfer-answer-key.json');numeric=[];proof=[]
    for arm in args.arms:
        reference=op.O/f'transfer-reference-{arm}-{args.cap}.json'
        folder=Path(op.read(reference)['directory']) if reference.exists() else op.O/(f'{arm}-transfer'+('' if args.cap==32768 else '-'+str(args.cap)))
        for j in jobs:
            if j['id'] in args.exclude_jobs:continue
            f=folder/(j['id']+'-0.json')
            if not f.exists():continue
            r=op.read(f);assert r['messages']==j['messages'] and r['seed']==j['seed']
            row={'arm':arm,'job_id':j['id'],'source_id':j['source_id'],'split':j['split'],'cap':args.cap,
                 'file':str(f),'file_sha256':op.sha(f),'finish_reason':r['finish_reason'],'tokens':len(r['completion_ids'])}
            if j['split']=='proof':proof.append(row);continue
            target=float(sc.parse_numeric(key[j['id']]['answer_exact']));parsed,method,excerpt=sc.parse(r['raw_text']);value=None
            if parsed is not None:
                try:
                    v=float(sc.parse_numeric(parsed))
                    if math.isfinite(v):value=v
                except (ValueError,TypeError,OverflowError):pass
            row.update(target=target,value=value,numeric_correct=None if value is None else abs(value-target)<=1e-4 or abs(value-target)/abs(target)<=1e-5,
                       parse_method=method,answer_excerpt=excerpt[-700:]);numeric.append(row)
    op.write(out,{'status':'partial','numeric':numeric,'proof':proof,'note':'Provisional cap; only identical final content may inherit a grade.'})
    print(str(out),len(numeric),len(proof))
if __name__=='__main__':main()
