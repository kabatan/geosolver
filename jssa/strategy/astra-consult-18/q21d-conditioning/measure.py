"""Small read-only reanalysis of saved correct endpoints; writes HERE only."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
import traceback

for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
from mpmath import mp
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.refinement.mpmath_refiner import _smooth_zero_constraint_residuals
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode


def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, np.ndarray):
        return clean(v.tolist())
    if isinstance(v, np.generic):
        return clean(v.item())
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def write_json(name, value):
    (HERE / name).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2) + '\n')


def source_hashes():
    paths = [HERE / 'protocol.md', HERE / 'measure.py', ROOT / 'benchmarks/cases.jsonl',
             ROOT / 'jssa/difficulty/minima/basins-323.csv',
             ROOT / 'jssa/difficulty/ghost-1023/human_feat.csv',
             ROOT / 'jssa/results/stage-profile-20261023/per-case.csv']
    paths += sorted((ROOT / 'src').rglob('*.py'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def make_evaluator(dsl):
    bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    return bundle, build_ir_evaluator(bundle)


def eval_ft(bundle, ev, x, smooth=True, dps=60):
    # Conversion to float occurs outside the guarded HP block.
    decimal_x = [repr(float(v)) for v in x]
    with mp.workdps(dps), high_precision_mode():
        point = [mp.mpf(v) for v in decimal_x]
        raw = ev.evaluate_hp_residual(point, precision=dps).residual_vector
        vals = _smooth_zero_constraint_residuals(bundle=bundle, point=point, dps=dps, residuals=raw) if smooth else raw
        target = ev.evaluate_answer_hp(point, precision=dps).answer_hp
    f = np.asarray([float(v) for v in vals], dtype=float)
    t = float(target)
    if not np.all(np.isfinite(f)) or not math.isfinite(t):
        raise ValueError('nonfinite evaluation')
    return f, t


def raw_f(ev, x):
    return np.asarray(ev.evaluate_float_residual(list(map(float, x))).residual_vector, dtype=float)


def differential(bundle, ev, x, scales, h):
    f0, t0 = eval_ft(bundle, ev, x)
    cols, grads, one_sided = [], [], []
    for j in range(len(x)):
        dx = np.zeros(len(x)); dx[j] = h * scales[j]
        fp, tp = eval_ft(bundle, ev, x + dx)
        fm, tm = eval_ft(bundle, ev, x - dx)
        cols.append((fp - fm) / (2*h))
        grads.append((tp - tm) / (2*h))
        one_sided.append((fp + fm - 2*f0) / h)
    return np.column_stack(cols), np.asarray(grads), np.column_stack(one_sided)


def metric(J, g, target, row_weights):
    A = row_weights[:, None] * J
    u, s, vh = np.linalg.svd(A, full_matrices=False)
    threshold = max(1e-10, 1e-7*s[0]) if len(s) else 1e-10
    rank = int(np.sum(s > threshold))
    n = J.shape[1]
    result = dict(rank=rank, n=n, svals=s.tolist(), full_rank=(rank == n))
    if rank < n:
        return result
    gain = np.linalg.norm((g @ vh.T) / s)
    gn = np.linalg.norm(g)
    kx = 1/s[-1]
    result.update(cond=s[0]/s[-1], kx=kx, ktau=gain/max(1,abs(target)),
                  grad_norm=gn, q=(gain/(gn*kx) if gn else None),
                  weak_alignment=(abs(g @ vh[-1])/gn if gn else None),
                  weak_direction=vh[-1].tolist(), smin=s[-1], smax=s[0])
    return result


def measure(case):
    tstart = time.monotonic()
    cid = case['id']
    out = {'id': cid, 'dsl_sha256': hashlib.sha256(json.dumps(case['dsl'], sort_keys=True).encode()).hexdigest()}
    path = ROOT / 'jssa/difficulty/minima/raw-323' / (cid + '.json')
    if not path.exists():
        return dict(out, status='missing_raw')
    out['raw_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    raw = json.loads(path.read_text())
    out['n_vars'] = raw.get('n_vars')
    if not raw.get('n_vars'):
        return dict(out, status='no_variables')
    hits = [r for r in raw.get('records', []) if r.get('cls') == 'hit' and 'x' in r]
    out['n_hits'] = len(hits)
    if not hits:
        return dict(out, status='no_saved_hit')
    rec = min(hits, key=lambda r:r['k'])
    x = np.asarray(rec['x'], dtype=float)
    b, ev = make_evaluator(case['dsl'])
    out.update(variables=list(b.var_names), x=x.tolist(), hit_k=rec['k'])
    fraw = raw_f(ev, x)
    f0, t0 = eval_ft(b, ev, x)
    hard = bool(ev.evaluate_float_hard_feasibility(x.tolist(), include_margins=False).hard_feasible)
    guard = bool(ev.evaluate_guard(x.tolist())[0])
    out.update(raw_residual_max=np.max(np.abs(fraw), initial=0), smooth_residual_max=np.max(np.abs(f0), initial=0),
               target=t0, hard=hard, guard=guard, n_raw=len(fraw), n_smooth=len(f0))
    if not hard or not guard or not np.all(np.isfinite(fraw)) or out['raw_residual_max'] > 1e-8:
        return dict(out, status='saved_hit_failed_reevaluation')
    D = np.maximum(1., np.abs(x))
    ds = [differential(b, ev, x, D, h) for h in (1e-5, 1e-6, 1e-7)]
    weights = 1 / np.maximum(1., np.linalg.norm(ds[1][0], axis=1))
    ms = [metric(j, g, t0, weights) for j, g, _ in ds]
    out.update(scales=D, row_weights=weights, differentials=ms,
               jacobian=ds[1][0], gradient=ds[1][1])
    J, g, _ = ds[1]
    # Secondary metric: unmodified float residual in the same variable scale.
    jr = []
    for j in range(len(x)):
        dx = np.zeros(len(x)); dx[j] = 1e-6 * D[j]
        jr.append((raw_f(ev, x+dx)-raw_f(ev, x-dx))/(2e-6))
    Jr = np.column_stack(jr)
    wr = 1/np.maximum(1.,np.linalg.norm(Jr,axis=1))
    out['raw_metric'] = metric(Jr, g, t0, wr)
    # A second, independently fixed coordinate scaling diagnoses scale dependence.
    box = np.asarray(raw['box'], dtype=float)
    Db = np.maximum(box[:, 1]-box[:, 0], 1e-12)
    Jb, gb = J * (Db/D)[None, :], g * (Db/D)
    wb = 1/np.maximum(1.,np.linalg.norm(Jb,axis=1))
    out['box_metric'] = metric(Jb, gb, t0, wb)
    one_sided = max(np.linalg.norm(weights[:,None]*d[2]) / max(np.linalg.norm(weights[:,None]*d[0]), 1e-30) for d in ds)
    grad_var = max(np.linalg.norm(d[1]-g)/max(np.linalg.norm(g),1e-10) for d in ds)
    out.update(one_sided_ratio=one_sided, gradient_relative_variation=grad_var,
               elapsed_s=time.monotonic()-tstart)
    if not all(m['full_rank'] for m in ms):
        out['status'] = 'rank_deficient_or_rank_unstable'
    elif max(m['cond'] for m in ms)/min(m['cond'] for m in ms)>1.25 or grad_var>.01 or one_sided>.01:
        out['status'] = 'differential_unstable'
    elif np.linalg.norm(g)/max(1,abs(t0))<=1e-10:
        out['status'] = 'near_zero_gradient'
    else:
        out['status'] = 'regular_stable'
    out['main'] = ms[1]
    return out


def timeout(signum, frame):
    raise TimeoutError('25 second case limit')


def main():
    manifest = source_hashes()
    write_json('measurement-lock.json', {'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()), 'hashes':manifest})
    cases = sorted([json.loads(s) for s in (ROOT/'benchmarks/cases.jsonl').read_text().splitlines() if s.strip()],key=lambda c:c['id'])
    signal.signal(signal.SIGALRM, timeout)
    t0 = time.monotonic()
    out = []
    for i, case in enumerate(cases):
        if time.monotonic()-t0>3600:
            out.append({'id':case['id'],'status':'global_budget'})
            continue
        signal.alarm(25)
        try:
            result = measure(case)
        except Exception as e:
            result = {'id':case['id'],'status':'error','error':str(e),'error_type':type(e).__name__,'traceback':traceback.format_exc(limit=3)}
        finally:
            signal.alarm(0)
        out.append(clean(result))
        if (i+1)%25==0:
            from collections import Counter
            print(json.dumps({'done':i+1,'elapsed_s':time.monotonic()-t0,'statuses':dict(Counter(x['status'] for x in out))}),flush=True)
    write_json('measurements.json',out)
    write_json('measurement-completion.json',{'elapsed_s':time.monotonic()-t0,'n':len(out),
                                             'unchanged_sources':source_hashes()==manifest})
    print(json.dumps({'complete':len(out),'elapsed_s':time.monotonic()-t0}),flush=True)


if __name__ == '__main__':
    main()
