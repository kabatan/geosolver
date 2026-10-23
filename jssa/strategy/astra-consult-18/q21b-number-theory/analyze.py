"""Q21b small, read-only-source reconstruction experiments. No local search."""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import sys
import time
from contextlib import contextmanager
from collections import Counter, defaultdict
from datetime import datetime, timezone

import mpmath as mpm
from mpmath import mp
import sympy as sp

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
X = sp.Symbol('x')
GRID = [10, 15, 20, 30, 40, 50, 60, 80, 100, 120]


class BudgetExpired(BaseException):
    pass


@contextmanager
def limit(seconds):
    def expired(*_):
        raise BudgetExpired('fixed wall budget exceeded')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jsave(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def csave(name, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def loadcsv(path):
    return list(csv.DictReader(Path(path).open()))


def parser():
    # Reuse just the repository's reference-notation normalizer; no main runs.
    tree = ast.parse((ROOT / 'jssa/difficulty/probe_basins.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_ascii_expr')
    env = {'re': re}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<existing _ascii_expr>', 'exec'), env)
    return env['_ascii_expr']


def answer_exprs(answer):
    normalize = parser()
    items = answer if isinstance(answer, list) else [answer]
    result = []
    for item in items:
        text = re.sub(r'\(\d+個\)', '', str(item))
        for part in text.split(',') if 'CRootOf' not in text else [text]:
            if part.strip():
                expr = sp.sympify(normalize(part), locals={'cbrt': sp.cbrt, 'CRootOf': sp.CRootOf}, rational=True)
                result.append((part, expr))
    return result


def primitive(expr):
    p = sp.Poly(expr, X, domain=sp.QQ).clear_denoms()[1].primitive()[1]
    c = [int(v) for v in p.all_coeffs()]
    return [-v for v in c] if c[0] < 0 else c


def depth(expr):
    sub = max((depth(a) for a in expr.args), default=0)
    return sub + int(expr.is_Pow and expr.exp.is_Rational and expr.exp.q > 1)


def census():
    cases = [json.loads(l) for l in (ROOT / 'benchmarks/cases.jsonl').read_text().splitlines() if l]
    human = {r['case_id']: r for r in loadcsv(ROOT / 'jssa/difficulty/ghost-1023/human_feat.csv')}
    basins = {r['id']: r for r in loadcsv(ROOT / 'jssa/difficulty/minima/basins-323.csv')}
    old = {r['case_id']: r for r in loadcsv(ROOT / 'jssa/difficulty/dissociation/answer-poly.csv')}
    values, problems, errors = [], [], []
    for case in cases:
        local = []
        try:
            expressions = answer_exprs(case['answer'])
        except Exception as e:
            errors.append({'id': case['id'], 'stage': 'parse', 'error': repr(e)})
            expressions = []
        for j, (source, expr) in enumerate(expressions):
            r = {'id': case['id'], 'answer_index': j, 'source_expression': source, 'expression': str(expr),
                 'radical_depth': depth(expr), 'has_pi': expr.has(sp.pi), 'status': 'ok'}
            try:
                with limit(5):
                    r['value_180'] = str(sp.N(expr, 180))
                    if not r['has_pi']:
                        coeff = primitive(sp.minimal_polynomial(expr, X))
                        d, h = len(coeff) - 1, max(map(abs, coeff))
                        r.update(coefficients=coeff, degree=d, height=h,
                                 log10_height=math.log10(h),
                                 heuristic_digits=(d+1)*math.log10(max(2,h)))
                        # KLL Thm 1.19: 2^s > 2^(d^2/2)(d+1)^((3d+4)/2)H^(2d),
                        # |a-a_tilde| < 2^-s/(12d). Strict s converted to decimals.
                        sbits = math.floor(d*d/2 + (3*d+4)/2*math.log2(d+1) + 2*d*math.log2(h)) + 1
                        r['kll_bits_s'] = sbits
                        r['kll_absolute_digits'] = math.ceil(sbits*math.log10(2)+math.log10(12*d))
            except (Exception, BudgetExpired) as e:
                r.update(status='error', error=repr(e))
                errors.append({'id': case['id'], 'answer_index': j, 'stage': 'minpoly', 'error': repr(e)})
            values.append(r)
            local.append(r)
        good = [r for r in local if 'degree' in r]
        hm, ba = human.get(case['id'], {}), basins.get(case['id'], {})
        pr = {'id': case['id'], 'n_answers': len(local), 'algebraic_answers': len(good),
              'has_pi': any(r['has_pi'] for r in local), 'degree': max((r['degree'] for r in good), default=''),
              'height': max((r['height'] for r in good), default=''),
              'heuristic_digits': max((r['heuristic_digits'] for r in good), default=''),
              'kll_absolute_digits': max((r['kll_absolute_digits'] for r in good), default=''),
              'radical_depth': max((r['radical_depth'] for r in local), default=''),
              'contest': hm.get('contest',''), 'human': hm.get('human',''), 'n_vars': ba.get('n_vars',''),
              'local_p': ba.get('p',''), 'n_starts': ba.get('n_starts','')}
        pr['old_degree_agrees'] = str(pr['degree']) == old.get(case['id'], {}).get('deg', '')
        pr['old_height_agrees'] = str(pr['height']) == old.get(case['id'], {}).get('height', '')
        problems.append(pr)
    jsave('values.json', values)
    csave('answer-census.csv', problems)
    csave('answer-values.csv', [{**r, 'coefficients': json.dumps(r.get('coefficients'))} for r in values])
    src_hashes = {str(p.relative_to(ROOT)): digest(p) for p in sorted((ROOT/'src').rglob('*.py'))}
    manifest = {'time_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.executable,
                'sympy': sp.__version__, 'mpmath': mpm.__version__, 'protocol_sha256': digest(OUT/'protocol.md'),
                'source_hashes': src_hashes,
                'input_hashes': {p: digest(ROOT/p) for p in ['benchmarks/cases.jsonl',
                  'jssa/difficulty/ghost-1023/human_feat.csv', 'jssa/difficulty/minima/basins-323.csv',
                  'jssa/difficulty/dissociation/answer-poly.csv', 'jssa/difficulty/certify-all/per-case.csv']},
                'script_sha256_at_census': digest(__file__)}
    jsave('manifest.json', manifest)
    summary = {'problems': len(problems), 'values': len(values), 'errors': errors,
               'problem_degrees': dict(Counter(r['degree'] for r in problems)),
               'value_degrees': dict(Counter(r.get('degree', 'pi') for r in values)),
               'depths': dict(Counter(r['radical_depth'] for r in problems)),
               'old_disagreements': [r for r in problems if not r['has_pi'] and (not r['old_degree_agrees'] or not r['old_height_agrees'])],
               'largest_heuristic': sorted([r for r in values if 'degree' in r],key=lambda r:r['heuristic_digits'],reverse=True)[:5]}
    jsave('census-summary.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='largest_heuristic'},ensure_ascii=False),flush=True)


def reconstruct(value, precision, expected, *, max_degree=8, max_coeff=10**8, max_steps=20000):
    from geosolver.exact.polynomial_search import find_minimal_polynomial
    start = time.monotonic()
    try:
        with limit(2), mp.workdps(max(80, precision+40)):
            # Freeze to p significant decimal digits; extra working digits add no information.
            rounded = mp.mpf(mp.nstr(mp.mpf(value), precision))
            got = find_minimal_polynomial(rounded, precision=precision, max_degree=max_degree,
                                          max_coeff=max_coeff, max_steps=max_steps)
        status = 'correct' if got == expected else ('none' if got is None else 'wrong')
        return {'status': status, 'got': got, 'seconds': time.monotonic()-start}
    except BudgetExpired:
        return {'status': 'timeout', 'got': None, 'seconds': time.monotonic()-start}
    except Exception as e:
        return {'status': 'error', 'got': None, 'error':repr(e), 'seconds': time.monotonic()-start}


def precision():
    values = json.loads((OUT/'values.json').read_text())
    rows = []
    start = time.monotonic()
    path = OUT/'precision.jsonl'
    with path.open('w') as f:
        for p in GRID:
            sub = []
            for v in values:
                if 'coefficients' not in v:
                    continue
                if time.monotonic()-start > 1200:
                    jsave('precision-budget-stop.json', {'time': time.monotonic()-start, 'next_p': p, 'next_id':v['id']})
                    csave('precision.csv', rows)
                    return
                row = {'id':v['id'],'answer_index':v['answer_index'],'precision':p,
                       **reconstruct(v['value_180'],p,v['coefficients'])}
                f.write(json.dumps(row)+'\n'); f.flush()
                rows.append(row); sub.append(row)
            print('p',p,'counts',dict(Counter(r['status'] for r in sub)), 'elapsed',round(time.monotonic()-start,2),flush=True)
    csave('precision.csv',rows)
    jsave('precision-timing.json', {'elapsed_seconds':time.monotonic()-start, 'calls':len(rows)})


def saved_and_replay():
    values = [v for v in json.loads((OUT/'values.json').read_text()) if 'coefficients' in v]
    byid = defaultdict(list)
    for v in values:
        byid[v['id']].append(v)
    cert_root = ROOT/'jssa/difficulty/certify-all'
    candidates, selected, manifest = [], [], []
    for row in loadcsv(cert_root/'per-case.csv'):
        if row['id'] not in byid:
            continue
        path = cert_root / row['result_path']
        data = json.loads(path.read_text())
        manifest.append({'id':row['id'],'path':str(path.relative_to(ROOT)),'sha256':digest(path)})
        for j,c in enumerate(data.get('candidates',[])):
            if not c.get('hp_value'):
                continue
            try:
                with mp.workdps(180):
                    val = mp.mpf(c['hp_value'])
                    vv = min(byid[row['id']],key=lambda v:abs(val-mp.mpf(v['value_180'])))
                    err = abs(val-mp.mpf(vv['value_180'])) / max(1,abs(mp.mpf(vv['value_180'])))
                    digits = 180.0 if err==0 else float(-mp.log10(err))
                candidates.append({'id':row['id'], 'candidate_index':j, 'answer_index':vv['answer_index'],
                    'degree':vv['degree'], 'relative_digits':digits, 'hp_value':c['hp_value'],
                    'proposal_kind':c.get('proposal_kind'), 'candidate_status':c.get('candidate_status'),
                    'hp_residual':c.get('hp_residual'), 'source_path':str(path.relative_to(ROOT))})
            except Exception as e:
                candidates.append({'id':row['id'],'candidate_index':j,'error':repr(e)})
    for d in range(1,5):
        seen = set()
        for c in sorted(candidates,key=lambda c:(c['id'],c['candidate_index'])):
            if c.get('degree')==d and c.get('relative_digits',0)>=80 and c['id'] not in seen:
                seen.add(c['id']);selected.append(c)
                if len(seen)==2:
                    break
    jsave('saved-candidate-manifest.json',manifest)
    csave('saved-candidates.csv',candidates)
    jsave('replay-selection.json',selected)
    # Selection is saved before new reconstruction calls.
    rows = []
    for c in selected:
        v = next(v for v in byid[c['id']] if v['answer_index']==c['answer_index'])
        expr=sp.sympify(v['expression'],locals={'x':X})
        for q in [1,1009,1000003]:
            shifted = expr if q==1 else expr+sp.Rational(1,q)
            coeff = primitive(sp.minimal_polynomial(shifted,X))
            dd, hh = len(coeff)-1,max(map(abs,coeff))
            q_not_divides_lc = q!=1 and v['coefficients'][0]%q!=0
            blocked = q_not_divides_lc and q**v['degree'] > 10**8
            # Explicitly check every power-of-ten scale used by the repository.
            from geosolver.exact.polynomial_search_helpers import scale_candidates_for_value
            scales=[]
            with mp.workdps(180):
                ideal=str(sp.N(shifted,180))
                saved_val=mp.mpf(c['hp_value'])+(mp.mpf(1)/q if q!=1 else 0)
                saved_str=mp.nstr(saved_val,180)
                for scale in scale_candidates_for_value(mp.mpf(ideal)):
                    k=int(mp.nint(mp.log10(scale)))
                    pc=primitive(sum(sp.Integer(a)*(X*(sp.Rational(10)**k))**(dd-i) for i,a in enumerate(coeff)))
                    scales.append({'exponent':k,'height':max(map(abs,pc)), 'leading':pc[0]})
            for origin,p,vs in [('saved',80,saved_str),('oracle',80,ideal),('oracle',120,ideal)]:
                rr={'id':c['id'],'answer_index':v['answer_index'],'degree':dd,'q':q,'height':hh,
                    'original_height':v['height'],'origin':origin,'precision':p,
                    'q_not_divides_original_lc':q_not_divides_lc,'blocked_by_q_power':blocked,
                    'min_scaled_height':min(s['height'] for s in scales),
                    'expression':str(shifted),'expected':coeff,
                    **reconstruct(vs,p,coeff)}
                rows.append(rr)
            print('replay',c['id'],'q',q,'statuses',[r['status'] for r in rows[-3:]],flush=True)
    csave('recoding-replay.csv',rows)
    jsave('recoding-replay.json',rows)
    jsave('saved-summary.json',{'candidates_with_hp':len(candidates),'problems_with_hp':len({c['id'] for c in candidates}),
         'candidates_80_digits':sum(c.get('relative_digits',0)>=80 for c in candidates),
         'problems_80_digits':len({c['id'] for c in candidates if c.get('relative_digits',0)>=80}),
         'selected_problems':len(selected),'degree_selection':dict(Counter(c['degree'] for c in selected)),
         'replay_statuses':dict(Counter(r['status'] for r in rows))})


def main():
    a=argparse.ArgumentParser();a.add_argument('phase',choices=['census','precision','replay']);args=a.parse_args()
    {'census':census,'precision':precision,'replay':saved_and_replay}[args.phase]()


if __name__=='__main__':
    main()
