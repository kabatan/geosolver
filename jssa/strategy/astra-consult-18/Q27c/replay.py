"""Registered fixed-input PSLQ diagnostic; no local search or source edits."""
from __future__ import annotations

import csv
import hashlib
import json
import random
import signal
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from mpmath import mp
from geosolver.exact.polynomial_search import find_minimal_polynomial

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


class Timeout(BaseException):
    pass


def alarm(*_):
    raise Timeout()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    started = time.monotonic()
    values_path = ROOT / 'jssa/strategy/astra-consult-18/q21b-number-theory/values.json'
    values = sorted([v for v in json.loads(values_path.read_text()) if v.get('degree',0)>=2],
                    key=lambda v:(v['id'],v['answer_index']))
    assert len(values)==131 and len({v['id'] for v in values})==127
    inputs = []
    with mp.workdps(180):
        for seed in [270023,270024]:
            rng = random.Random(seed)
            for v in values:
                base = mp.mpf(mp.nstr(mp.mpf(v['value_180']),140))
                u = mp.mpf(rng.uniform(-1,1))
                a = base + u*mp.power(10,-130)*max(1,abs(base))
                inputs.append(dict(seed=seed, id=v['id'], answer_index=v['answer_index'],
                    degree=v['degree'], expected=v['coefficients'], value=mp.nstr(a,180)))
    lock = dict(utc=datetime.now(timezone.utc).isoformat(), python=sys.executable,
        preregistration_sha256=sha(OUT/'preregistration.md'), script_sha256=sha(Path(__file__)),
        values_sha256=sha(values_path),
        source_sha256=sha(ROOT/'src/geosolver/exact/polynomial_search.py'),
        helpers_sha256=sha(ROOT/'src/geosolver/exact/polynomial_search_helpers.py'),
        planned_calls=786, mpmath_version=__import__('mpmath').__version__)
    (OUT/'replay-lock.json').write_text(json.dumps(lock,indent=2)+'\n')
    (OUT/'replay-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    signal.signal(signal.SIGALRM, alarm)
    records = []
    stopped = False
    with (OUT/'replay.csv').open('w',newline='') as f:
        fields=['id','answer_index','degree','seed','declared_precision','status','got','seconds']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for inp in inputs:
            for p in [40,80,101]:
                if time.monotonic()-started>=180:
                    stopped=True
                    break
                row = {k:inp[k] for k in ['id','answer_index','degree','seed']}
                row['declared_precision']=p
                t=time.monotonic()
                got=None
                signal.setitimer(signal.ITIMER_REAL,min(2,180-(t-started)))
                try:
                    with mp.workdps(180):
                        got=find_minimal_polynomial(mp.mpf(inp['value']), precision=p,
                                max_degree=8, max_coeff=10**8, max_steps=20000)
                    status='correct' if got==inp['expected'] else ('none' if got is None else 'wrong')
                except Timeout:
                    status='timeout'
                except Exception as e:
                    status='error:'+type(e).__name__
                finally:
                    signal.setitimer(signal.ITIMER_REAL,0)
                row.update(status=status,got=json.dumps(got),seconds=time.monotonic()-t)
                writer.writerow(row);f.flush();records.append(row)
            if stopped:break
    by={}
    for r in records:
        by.setdefault((r['id'],r['answer_index'],r['declared_precision']),[]).append(r)
    mismatches=[list(k) for k,z in by.items() if len(z)!=2 or
                len({(r['status'],r['got']) for r in z})!=1]
    counts={str(seed):{str(p):dict(Counter(r['status'] for r in records
                       if r['seed']==seed and r['declared_precision']==p)) for p in [40,80,101]}
            for seed in [270023,270024]}
    fourth={str(seed):{str(p):dict(Counter(r['status'] for r in records
                      if r['seed']==seed and r['declared_precision']==p and r['degree']==4))
                      for p in [80,101]} for seed in [270023,270024]}
    complete=len(records)==786
    summary=dict(actual_calls=len(records), planned_calls=786, complete=complete,
        elapsed_seconds=time.monotonic()-started, counts=counts, fourth_degree_counts=fourth,
        paired_mismatches=mismatches,
        P1=complete and all(fourth[str(s)]['80'].get('wrong',0)>=3 and
            fourth[str(s)]['101'].get('correct',0)==8 for s in [270023,270024]),
        P2=complete and len(by)==393 and not mismatches,
        P3=complete and all(counts[str(s)]['101'].get('correct',0)==131 for s in [270023,270024]))
    (OUT/'replay-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    main()
