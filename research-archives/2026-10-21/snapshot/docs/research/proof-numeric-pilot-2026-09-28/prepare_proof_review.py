"""Start blinded proof review while independent numeric generation is running.

Only usable when all 16 initial proofs ended naturally. Final aggregation must
verify these files are byte-identical to the final selected blind packet.
"""
import hashlib
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'qwen/.runtime/proof_numeric_pilot_20260928'


def read(p):return json.loads(p.read_text())


def main():
    jobs=read(OUT/'proof-jobs.json')
    assert len(jobs)==8
    for arm in ['base','sft']:
        receipt=read(OUT/f'{arm}-proof/receipt.json')
        assert receipt['status']=='complete' and receipt['completed_jobs']==8
        assert receipt['jobs_sha256']==hashlib.sha256((OUT/'proof-jobs.json').read_bytes()).hexdigest()
        for job in jobs:
            assert read(OUT/f'{arm}-proof'/f"{job['id']}-0.json")['finish_reason']=='stop', 'extension needed before grading'
    folder=OUT/'proof-review';folder.mkdir(exist_ok=False)
    entries=[(arm,j) for arm in ['base','sft'] for j in jobs]
    random.Random(2026092899).shuffle(entries)
    index=[]
    for idx,(arm,job) in enumerate(entries):
        raw=read(OUT/f'{arm}-proof'/f"{job['id']}-0.json");cid=f'proof-{idx:02d}'
        row={'case_id':cid,'messages':raw['messages'],'raw_text':raw['raw_text'],
             'final_text':raw['final_text'],'finish_reason':raw['finish_reason'],'tokens':len(raw['completion_ids'])}
        path=folder/f'{cid}.json'
        path.write_text(json.dumps(row,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        index.append({'case_id':cid,'file':str(path),'tokens':row['tokens'],
                      'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (folder/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    print(json.dumps({'status':'ready','cases':len(index),'index':str(folder/'index.json')}))


if __name__=='__main__':main()
