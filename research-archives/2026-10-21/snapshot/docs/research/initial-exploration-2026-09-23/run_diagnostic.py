"""Adaptive inference-only diagnostics, bounded by 4h for the entire pilot."""
import argparse
import json
import sys
import time
from pathlib import Path
from qwen.common import write_json, file_hash, now
from qwen.grpo_run import run_worker
HERE=Path(__file__).resolve().parent
ROOT=Path('qwen/.runtime/exp04_exploration')

def main():
    ap=argparse.ArgumentParser(__doc__)
    ap.add_argument('stage',choices=['clarification','meaningful'])
    args=ap.parse_args()
    assert (HERE/'grading-freeze.json').exists(), 'Finish primary grading first'
    primary=json.loads((ROOT/'worker_receipt.json').read_text())
    assert primary['status']=='complete'
    used=primary['elapsed_seconds']
    for p in ROOT.glob('diagnostic-*/worker_receipt.json'):
        r=json.loads(p.read_text());assert r['status']=='complete',f'Inspect unfinished diagnostic: {p}'
        used+=r['elapsed_seconds']
    remaining=14400-used
    assert remaining>60, 'Overall 4 GPU-worker-hour exploratory budget exhausted'
    if args.stage=='clarification':
        jobs=HERE/'h04-clarification-jobs.json';samples=4;cap=32512;seed=2026092302
    else:
        jobs=HERE/'meaningful-jobs.json';samples=4;cap=32512;seed=2026092303
    out=ROOT/('diagnostic-'+args.stage)
    out.mkdir(parents=True,exist_ok=True)
    receipt=out/'worker_receipt.json'
    assert not receipt.exists(), 'Inspect existing receipt; do not silently repeat a run'
    command=[sys.executable,'-m','qwen.grpo_stage','generate','--route','fp16_native','--jobs',str(jobs),'--output',str(out/'generation'),'--samples',str(samples),'--seed',str(seed),'--max-seqs','4','--max-completion',str(cap)]
    record={'stage':args.stage,'start_utc':now(),'status':'running','command':command,'jobs_sha256':file_hash(jobs),'driver_sha256':file_hash(__file__),'remaining_overall_seconds_at_start':remaining,'updates':0}
    write_json(receipt,record);start=time.monotonic()
    try:
        run_worker(command,out/'generate.log',remaining);record['status']='complete'
    except BaseException as e:
        record['status']='failed';record['error']=str(e);raise
    finally:
        record['end_utc']=now();record['elapsed_seconds']=time.monotonic()-start
        write_json(receipt,record);print(json.dumps(record,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
