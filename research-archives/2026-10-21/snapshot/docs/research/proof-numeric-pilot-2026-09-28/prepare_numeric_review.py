"""Blind naturally completed numeric pairs while common extensions run."""
import hashlib
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'qwen/.runtime/proof_numeric_pilot_20260928'


def read(p):return json.loads(p.read_text())


def main():
    jobs=read(OUT/'data/numeric-jobs.json');assert len(jobs)==12
    selected=set()
    for arm in ['base','sft']:
        receipt=read(OUT/f'{arm}-numeric/receipt.json')
        assert receipt['status']=='complete' and receipt['completed_jobs']==12
        assert receipt['jobs_sha256']==hashlib.sha256((OUT/'data/numeric-jobs.json').read_bytes()).hexdigest()
        for job in jobs:
            if read(OUT/f'{arm}-numeric'/f"{job['id']}-0.json")['finish_reason']=='length':selected.add(job['id'])
    folder=OUT/'numeric-review';folder.mkdir(exist_ok=False)
    rng=random.Random(2026092899)
    previous=list(range(16));rng.shuffle(previous)  # identical advance as primary proof shuffle
    entries=[(arm,j) for arm in ['base','sft'] for j in jobs];rng.shuffle(entries)
    index=[]
    for idx,(arm,job) in enumerate(entries):
        if job['id'] in selected:continue
        raw=read(OUT/f'{arm}-numeric'/f"{job['id']}-0.json");cid=f'numeric-{idx:02d}'
        row={'case_id':cid,'messages':raw['messages'],'raw_text':raw['raw_text'],
             'final_text':raw['final_text'],'finish_reason':raw['finish_reason'],'tokens':len(raw['completion_ids'])}
        path=folder/f'{cid}.json';path.write_text(json.dumps(row,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        index.append({'case_id':cid,'file':str(path),'tokens':row['tokens'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (folder/'numeric-index.json').write_text(json.dumps(index,indent=2)+'\n')
    print(json.dumps({'ready':len(index),'pending_common_extension_pairs':len(selected)}))


if __name__=='__main__':main()
