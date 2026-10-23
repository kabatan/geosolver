"""Post-hoc smooth/high-precision audit; see diagnostic-protocol.md.

Run from repository root with the specified Python, -B, PYTHONPATH=src.
Only this directory is written. No global random search is performed.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
from concurrent.futures import ProcessPoolExecutor

for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'jssa/difficulty'))

import numpy as np
from scipy.optimize import least_squares
from mpmath import mp
from probe_basins import load_case, reference_values, answer_float
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot, evaluation_session
from geosolver.geometry.mp.mp_core_types import MPPoint
from geosolver.engine.standard.refinement.mpmath_refiner import _smooth_zero_constraint_residuals
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode


def alarm_handler(signum, frame):
    raise TimeoutError('180 second per-case limit')


def maxabs(x):
    return float(np.max(np.abs(x), initial=0.0))


def jacobian(fn, x, scales, h):
    f = fn(x)
    if len(f) == 0:
        return np.zeros((0, len(x)))
    cols = []
    for j in range(len(x)):
        xp, xm = x.copy(), x.copy()
        xp[j] += h * scales[j]
        xm[j] -= h * scales[j]
        cols.append((fn(xp) - fn(xm)) / (2*h))
    return np.column_stack(cols)


def rank_info(J, relative=1e-7):
    n = J.shape[1]
    if J.shape[0] == 0:
        return 0, np.array([]), np.eye(n), np.array([])
    row_scales = np.maximum(1.0, np.linalg.norm(J, axis=1))
    _, s, vh = np.linalg.svd(J / row_scales[:, None], full_matrices=True)
    threshold = max(1e-8, relative * float(s[0]) if len(s) else 0)
    rank = int(np.sum(s > threshold))
    return rank, s, vh[rank:].T, row_scales


def measure(cid):
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(180)
    started = time.monotonic()
    out = {'id': cid, 'protocol': 'diagnostic-protocol.md', 'samples': []}
    try:
        case = load_case(cid)
        b = load_problem_bundle(GeometryProblem.model_validate(case['dsl']).engine_document())
        ev = build_ir_evaluator(b)
        refs = reference_values(case['answer'])
        n = len(b.var_names)
        out.update(n_vars=n, variables=list(b.var_names), target=case['dsl']['target'], references=refs)

        def residual(x):
            with mp.workdps(80), high_precision_mode():
                point=[mp.mpf(repr(float(v))) for v in x]
                raw=ev.evaluate_hp_residual(point,precision=80).residual_vector
                smooth=_smooth_zero_constraint_residuals(bundle=b,point=point,dps=80,residuals=raw)
            return np.asarray([float(v) for v in smooth],dtype=float)

        def feasible(x):
            try:
                return bool(ev.evaluate_float_hard_feasibility(list(map(float, x)), include_margins=False).hard_feasible)
            except Exception:
                return False

        def state(x):
            f = np.asarray(ev.evaluate_float_residual(list(map(float,x))).residual_vector,dtype=float)
            v = answer_float(ev, x)
            return {'residual': maxabs(f), 'hard_feasible': feasible(x), 'answer': v,
                    'reference_matches': v is not None and any(abs(v-r) <= 1e-6*max(1.0,abs(r)) for r in refs),
                    'finite': bool(np.all(np.isfinite(f)))}

        def isgood(s):
            return s['finite'] and s['residual'] <= 1e-8 and s['hard_feasible']

        def figure(x):
            with mp.workprec(53), evaluation_session(ev):
                snap = numerical_snapshot(b.spec, b.var_names, list(map(float, x)), b.base_context, arithmetic='float')
                ctx = snap.materialize([item.name for item in b.spec.construction], partial=True)
                return {item.name: [float(ctx[item.name].x), float(ctx[item.name].y)]
                        for item in b.spec.construction if isinstance(ctx.get(item.name), MPPoint)}

        def shape(f, names):
            pts = np.asarray([f[k] for k in names], dtype=float)
            ds = np.asarray([np.sum((pts[i]-pts[j])**2) for i in range(len(pts)) for j in range(i+1,len(pts))])
            return ds / np.sum(ds) if np.sum(ds) > 0 else ds

        records = []
        best = []
        for folder in ('minima/raw-323', 'minima/raw-323-seed1',
                       'start-feasibility-1023/seed2-plain','start-feasibility-1023/seed2-feasible'):
            path = ROOT / 'jssa/difficulty' / folder / (cid+'.json')
            if not path.exists():
                continue
            data = json.loads(path.read_text())
            rr = [dict(r, source=folder) for r in data.get('records',[]) if 'x' in r and len(r['x'])==n]
            for r in data.get('first_hit',{}).values():
                if 'x' in r and len(r['x'])==n and not any(q.get('k')==r.get('k') for q in rr):
                    rr.append(dict(r,source=folder+':first_hit',cls='hit'))
            records.extend(r for r in rr if r['cls']=='hit')
            rr = [r for r in rr if math.isfinite(r.get('res',math.inf))]
            if rr:
                best.append(min(rr, key=lambda r:r.get('res',math.inf)))
        out['saved_hits'] = len(records)
        if not records and (HERE/'sources/analytic-witnesses.json').exists():
            analytic=json.loads((HERE/'sources/analytic-witnesses.json').read_text()).get(cid)
            if analytic:
                records.append({'x':analytic['x'],'source':'analytic-witnesses.json','cls':'analytic_witness','k':None})
        chosen = [records[i] for i in sorted(set((0,len(records)//2,len(records)-1)))] if records else best
        out['rank_at_saved_points'] = []
        roots = []
        for rec in chosen:
            x = np.asarray(rec['x'], dtype=float)
            sc = np.maximum(1.0,np.abs(x))
            before = state(x)
            try:
                J = jacobian(residual,x,sc,1e-6)
                _, _, _, rscale = rank_info(J)
                if len(rscale):
                    result = least_squares(lambda z:residual(x+sc*z)/rscale, np.zeros(n), method='trf',
                        max_nfev=400, ftol=1e-13,xtol=1e-13,gtol=1e-13)
                    candidate = x+sc*result.x
                    if isgood(state(candidate)):
                        x = candidate
            except (ValueError, np.linalg.LinAlgError, ZeroDivisionError):
                pass
            st = state(x)
            row = dict(source=rec['source'], k=rec.get('k'), original_class=rec['cls'], before=before, after=st)
            if isgood(st) and st['reference_matches']:
                sc = np.maximum(1.0,np.abs(x))
                rankrows=[]
                for h in (1e-5,1e-6,1e-7):
                    J=jacobian(residual,x,sc,h)
                    rank,s,_,_=rank_info(J)
                    rankrows.append({'h':h,'rank':rank,'nullity':n-rank,'svals':s.tolist(),
                        'rank_rtol_1e6':rank_info(J,1e-6)[0],'rank_rtol_1e8':rank_info(J,1e-8)[0]})
                row.update(x=x.tolist(), ranks=rankrows)
                roots.append((x,st,rankrows))
            out['rank_at_saved_points'].append(row)
        if not roots:
            out['status']='no_verified_local_seed'
            return out
        x0,st0,rankrows=roots[0]
        sc=np.maximum(1.0,np.abs(x0))
        J=jacobian(residual,x0,sc,1e-6)
        rank,s,N,rscale=rank_info(J)
        allr=[q['rank'] for _,_,rr in roots for q in rr]
        stable=len(set(allr))==1
        sensitive=all(q['rank']==q['rank_rtol_1e6']==q['rank_rtol_1e8'] for _,_,rr in roots for q in rr)
        out.update(x=x0.tolist(),base_state=st0,rank=rank,nullity=n-rank,rank_stable=stable,rank_threshold_stable=sensitive)
        f0=figure(x0)
        names=list(f0)
        shp0=shape(f0,names)
        out.update(point_names=names,figure=f0,shape=shp0.tolist())
        if n-rank==0:
            out['status']='locally_isolated' if stable and sensitive else 'rank_uncertain'
            return out
        # D(tau) on ker DF is descriptive only, not the constancy test.
        try:
            grad=jacobian(lambda x:np.asarray([answer_float(ev,x)]),x0,sc,1e-6)
            out['target_null_derivative']=maxabs(grad@N)
            ds=jacobian(lambda x:shape(figure(x),names),x0,sc,1e-6)
            out['shape_null_svals']=np.linalg.svd(ds@N,compute_uv=False).tolist()
        except Exception:
            out['shape_null_svals']=None
        directions=[]
        for j in range(min(N.shape[1],4)):
            group=[]
            for step in (1e-3,-1e-3,1e-2,-1e-2):
                wanted=np.zeros(N.shape[1]); wanted[j]=step
                def corr(z):
                    return np.concatenate((residual(x0+sc*z)/rscale if len(rscale) else np.array([]), N.T@z-wanted))
                rr={'direction':j,'step':step}
                try:
                    fit=least_squares(corr,N@wanted,method='trf',max_nfev=400,ftol=1e-13,xtol=1e-13,gtol=1e-13)
                    x=x0+sc*fit.x
                    st=state(x)
                    fig=figure(x)
                    shp=shape(fig,names)
                    coord=maxabs(N.T@fit.x-wanted)
                    rr.update(x=x.tolist(),state=st,figure=fig,shape_change=maxabs(shp-shp0),
                              target_relative_change=abs(st['answer']-st0['answer'])/max(1,abs(st0['answer'])) if st['answer'] is not None else None,
                              coordinate_error=coord, nfev=fit.nfev,
                              accepted=bool(isgood(st) and coord<=1e-8))
                except (ValueError,TypeError,ZeroDivisionError,KeyError,np.linalg.LinAlgError) as e:
                    rr.update(accepted=False,error=repr(e))
                out['samples'].append(rr);group.append(rr)
            good=all(q['accepted'] for q in group)
            moving=good and max(q.get('shape_change',0) for q in group)>=1e-5
            constant=good and max(q.get('target_relative_change',math.inf) for q in group)<=1e-7
            directions.append({'direction':j,'all_four_accepted':good,'shape_moves':moving,'target_constant':constant})
        out['directions']=directions
        accepted=[q for q in out['samples'] if q['accepted']]
        out['max_shape_change']=max((q['shape_change'] for q in accepted),default=None)
        out['max_target_relative_change']=max((q['target_relative_change'] for q in accepted),default=None)
        out['all_accepted_targets_constant']=bool(accepted and out['max_target_relative_change']<=1e-7)
        if stable and sensitive and any(d['shape_moves'] and d['target_constant'] for d in directions) and out['all_accepted_targets_constant']:
            out['status']='shape_motion_constant_target'
        elif stable and sensitive and any(d['all_four_accepted'] for d in directions) and not any(d['shape_moves'] for d in directions) and out['all_accepted_targets_constant']:
            out['status']='gauge_or_unseen_motion'
        else:
            out['status']='motion_or_rank_uncertain'
        return out
    except Exception as e:
        out.update(status='timeout' if isinstance(e,TimeoutError) else 'error',error=repr(e))
        return out
    finally:
        signal.alarm(0)
        out['seconds']=time.monotonic()-started


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('ids',nargs='*');ap.add_argument('--workers',type=int,default=2)
    args=ap.parse_args()
    if not 1<=args.workers<=2: raise ValueError('at most 2 workers')
    rows=list(csv.DictReader((HERE/'sources/comparison-cases.csv').open()))
    ids=args.ids or [r['id'] for r in rows if r['msolve_class'] in ('positive_dimensional','free_parameter')]
    outdir=HERE/'diagnostic';outdir.mkdir(exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for result in ex.map(measure,ids):
            (outdir/(result['id']+'.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
            print(result['id'],result['status'],result.get('nullity'),round(result['seconds'],3),flush=True)


if __name__=='__main__': main()
