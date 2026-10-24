"""Verify every observed candidate, with resumable disjoint 180-second slices."""
from __future__ import annotations
import json
import sys
import time
from stage2_common import *


def main(index):
    assert_identity()
    for name,sha in json.loads((OUT/'execution/full-implementation.lock.json').read_text())['files'].items():
        assert digest(OUT/name)==sha,name
    row=json.loads((RAW/'full-jobs.json').read_text())[index]
    d=RAW/'full'/f'{index:04d}'
    assert (d/'done.json').exists()
    assert not (d/'verification.json').exists()
    done=json.loads((d/'done.json').read_text())
    summary=json.loads((d/'observer-summary.json').read_text()) if (d/'observer-summary.json').exists() else None
    file=d/'candidates.jsonl'
    if not file.exists():
        save(d/'verification.json',dict(row,T=180,censored=True,reason='observation_missing',candidate_count=0,verified_count=0));return
    _,_,_,e=load_case(row['id'],row['arm'])
    out=d/'candidate-checks.jsonl';begun=d/'candidate-check-starts.jsonl'
    checked={int(json.loads(l)['index']):json.loads(l) for l in out.read_text().splitlines()} if out.exists() else {}
    starts={int(json.loads(l)['index']) for l in begun.read_text().splitlines()} if begun.exists() else set()
    t0=time.monotonic();n=0
    with file.open() as stream:
        for line in stream:
            rec=json.loads(line);n+=1;i=rec['index']
            if i in checked:continue
            if time.monotonic()-t0>=180:
                print(json.dumps({'index':index,'partial':True,'verified':len(checked)}));return
            if i in starts:
                check={'success':False,'reason':'verification_interrupted_no_retry'}
            else:
                append(begun,{'index':i,'utc':utc()})
                check=check_point(e,rec['x'])
            result={'index':i,'t':rec['t'],**check}
            append(out,result);checked[i]=result
    observation_ok=summary is not None and summary['errors']==0 and summary['candidates']==n
    crashing=(done.get('solver_status') not in ('solved','no_answer_found')
              and done.get('termination')!='time_limit_reached') or 'returncode' in done
    passed=[r['t'] for r in checked.values() if r['success'] and 0<=r['t']<180]
    found=bool(observation_ok and not crashing and passed)
    T=max(.001,min(passed)) if found else 180
    reason='found' if found else ('observation_incomplete' if not observation_ok else 'crash' if crashing else 'not_found')
    result=dict(row,T=T,censored=not found,reason=reason,candidate_count=n,verified_count=len(checked),
                successful_candidates=sum(r['success'] for r in checked.values()),
                observation_complete=observation_ok,solver_status=done.get('solver_status'),
                observer_summary=summary,completed_utc=utc())
    save(d/'verification.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main(int(sys.argv[1]))
