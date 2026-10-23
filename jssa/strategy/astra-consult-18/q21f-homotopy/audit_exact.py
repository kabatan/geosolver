"""Small rational Groebner audits; 30 seconds per fixed input, no source edits."""
import hashlib
import json
import signal
import time
from collections import deque
from pathlib import Path

import sympy as sp

OUT = Path(__file__).resolve().parent

def expire(*_):
    raise TimeoutError('fixed 30-second exact-audit deadline')

def quotient_dimension(G):
    if not G.is_zero_dimensional:
        return None
    leading = [tuple(p.LM(order=G.order).exponents) for p in G.polys]
    n = len(G.gens)
    todo = deque([tuple([0]*n)])
    seen, standard = set(), []
    while todo:
        mon = todo.popleft()
        if mon in seen:
            continue
        seen.add(mon)
        if any(all(a >= b for a,b in zip(mon,lm)) for lm in leading):
            continue
        standard.append(mon)
        if len(standard) > 1024:
            raise ValueError('quotient dimension exceeded audit cap')
        for j in range(n):
            q = list(mon); q[j] += 1; todo.append(tuple(q))
    return len(standard)

signal.signal(signal.SIGALRM, expire)
rows = []
for entry in json.loads((OUT/'prepared.json').read_text()):
    if not entry.get('eligible'):
        continue
    path = OUT/'inputs'/f"{entry['id']}__{entry['mode']}.json"
    data = json.loads(path.read_text())
    row = {'id':data['id'],'mode':data['mode'],
           'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    t0 = time.monotonic()
    signal.alarm(30)
    try:
        symbols = {v:sp.Symbol(v) for v in data['variables']}
        # Keep DSL coordinates after auxiliaries for interpretable elimination.
        names = [v for v in data['variables'] if not v.startswith('v_')]
        names += [v for v in data['variables'] if v.startswith('v_')]
        variables = [symbols[n] for n in names]
        eqs = [sp.sympify(e,locals=symbols) for e in data['equations']]
        G = sp.groebner(eqs,*variables,order='lex',domain=sp.QQ)
        row.update(status='ok',variables=names,zero_dimensional=G.is_zero_dimensional,
                   quotient_dimension_with_multiplicity=quotient_dimension(G),
                   groebner_basis=[str(p.as_expr()) for p in G.polys])
        row['univariate_factors'] = []
        for p in G.polys:
            expr = p.as_expr()
            if len(expr.free_symbols) != 1:
                continue
            v = next(iter(expr.free_symbols))
            poly = sp.Poly(expr,v)
            _, factors = sp.factor_list(poly)
            row['univariate_factors'].append({'variable':str(v),'polynomial':str(expr),
                'degree':poly.degree(),'squarefree_degree':poly.sqf_part().degree(),
                'factors':[[str(f.as_expr()),m] for f,m in factors],
                'distinct_real_roots':sum(len(f.intervals(eps=sp.Rational(1,10**20))) for f,_ in factors)})
        # Numeric roots of univariate factors are diagnostics; not a full system certificate.
    except Exception as e:
        row.update(status='error',error=f'{type(e).__name__}: {e}')
    finally:
        signal.alarm(0)
    row['seconds'] = time.monotonic()-t0
    rows.append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)
    (OUT/'exact-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
