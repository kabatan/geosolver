"""Fixed six-case polynomial preparation; does not run numerical searches."""
import hashlib
import json
import math
import signal
import sys
import time
from pathlib import Path

import sympy as sp

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
VENDOR = ROOT / 'jssa/strategy/astra-consult-17/H/sources'
sys.path.insert(0, str(VENDOR))
from algebraize import translate
from run_exact import build

IDS = ['AIME-2006-I-01','AIME-2025-I-06','AIME-2025-II-06',
       'HMMT-2010-FEB-GEO-02','HMMT-2014-FEB-GEO-08','JMO-2008-PRE-02']

def expired(*_):
    raise TimeoutError('preparation exceeded 60 seconds')

signal.signal(signal.SIGALRM, expired)
cases = {c['id']:c for c in map(json.loads,(ROOT/'benchmarks/cases.jsonl').read_text().splitlines())}
(OUT/'inputs').mkdir(exist_ok=True)
rows = []
for cid in IDS:
    case = cases[cid]
    for mode in ['fresh','inline']:
        start = time.monotonic()
        row = {'id':cid,'mode':mode,'status':'prepared'}
        signal.alarm(60)
        try:
            sys_, _ = translate(case['dsl'], mode=mode, with_target=False)
            eqs, used, factors = build(sys_, rabinowitsch=True)
            polys = [sp.Poly(e,*used,domain=sp.QQ) for e in eqs]
            degrees = [int(p.total_degree()) for p in polys]
            D = math.prod(degrees)
            row.update(nvars=len(used),neqs=len(eqs),degrees=degrees,total_degree_product=D,
                       dsl_variables=case['dsl']['variables'],variables=list(map(str,used)),
                       saturation_factors=list(map(str,factors)))
            eligible = len(used)==len(eqs) and len(used)<=10 and D<=512
            row['eligible'] = eligible
            row['selection_reason'] = 'within_fixed_caps' if eligible else 'outside_fixed_caps'
            data = dict(row, dsl=case['dsl'], equations=list(map(str,eqs)),
                        polynomials=[[[str(c),list(pows)] for pows,c in p.terms()] for p in polys],
                        angle_vars={str(k):list(map(str,v)) for k,v in sys_.angle_vars.items()})
            payload=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
            if len(payload.encode())>2*1024*1024:
                raise ValueError('input exceeds 2MiB')
            path=OUT/'inputs'/f'{cid}__{mode}.json'
            path.write_text(payload)
            row['input_sha256']=hashlib.sha256(payload.encode()).hexdigest()
        except Exception as e:
            row.update(status='error',error=f'{type(e).__name__}: {e}',eligible=False)
        finally:
            signal.alarm(0)
        row['prepare_seconds']=time.monotonic()-start
        rows.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
(OUT/'prepared.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
files=[OUT/'protocol.md',OUT/'prepare.py',ROOT/'benchmarks/cases.jsonl',
       ROOT/'jssa/difficulty/minima/basins-323.csv',VENDOR/'comparison-cases.csv',
       VENDOR/'algebraize.py',VENDOR/'run_exact.py']
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(OUT/'input-lock.json').write_text(json.dumps(manifest,indent=2)+'\n')
