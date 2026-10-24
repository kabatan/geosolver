"""Post-outcome Jacobians at the first (by k) five locally successful endpoints."""
from __future__ import annotations
import json
import sys
import time
from itertools import combinations
import numpy as np
from stage2_common import *


def prepare():
    local_jobs=json.loads((RAW/'local-jobs.json').read_text())
    full_jobs=json.loads((RAW/'full-jobs.json').read_text())
    assert all((RAW/'local'/f'{i:04d}'/'done.json').exists() for i in range(len(local_jobs)))
    assert all((RAW/'full'/f'{i:04d}'/'verification.json').exists() for i in range(len(full_jobs)))
    assert not (RAW/'jacobian-jobs.json').exists()
    success={}
    for f in sorted((RAW/'local').glob('*/records.jsonl')):
        for line in f.read_text().splitlines():
            row=json.loads(line)
            if row['success']:success.setdefault((row['id'],row['arm']),[]).append(row)
    jobs=[]
    for p in json.loads((OUT/'execution/lowering-audit.json').read_text()):
        cid=p['id']
        for arm in ARMS:
            for r in sorted(success.get((cid,arm),[]),key=lambda r:r['k'])[:5]:
                jobs.append({'id':cid,'arm':arm,'k':r['k'],'x':r['x']})
    save(RAW/'jacobian-jobs.json',jobs)
    save(RAW/'scaling-jobs.json',sorted({r['id'] for r in jobs}))
    save(OUT/'execution/jacobian-jobs.json',dict(utc=utc(),count=len(jobs),file=str(RAW/'jacobian-jobs.json'),sha256=digest(RAW/'jacobian-jobs.json'),
         selection='first five local successes ordered by k; no full-solver substitutions',
         rank_definition='number of singular values strictly exceeding sigma_max * 1e-8 (descriptive numerical rank)'))


def scaling(cid):
    path=RAW/'jacobian'/f'scaling-{cid}.json'
    if path.exists():return json.loads(path.read_text())
    prep=json.loads((RAW/'prepared'/f'{cid}.json').read_text())
    _,_,_,e=load_case(cid,'original')
    columns=[[] for _ in e.bundle.targets]
    missing=[0 for _ in columns]
    for x in prep['starts']:
        try:
            with limit(1):v=e.evaluate_float_residual(x).residual_vector
        except (Exception,MeasurementDeadline):v=[float('nan')]*len(columns)
        for i,value in enumerate(v):
            if math.isfinite(float(value)):columns[i].append(abs(float(value)))
            else:missing[i]+=1
    data={'id':cid,'center':[(a+b)/2 for a,b in prep['bounds']],
          'width':[b-a for a,b in prep['bounds']],
          'row_scales':[max(1.,float(np.median(v))) if v else 1. for v in columns],
          'finite_counts':[len(v) for v in columns],'all_nonfinite':[not v for v in columns],
          'row_map':list(range(len(columns))),
          'raw_equations':prep['arms']['original']['raw_equations']}
    save(path,data);return data


def efficacy(e,x,site):
    from mpmath import mp
    from geosolver.geometry.mp.mp_core_types import MPPoint
    from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot
    from geosolver.problem.ir.compiler import safe_eval_expr_hp
    b=e.bundle
    context=numerical_snapshot(b.spec,b.var_names,x,b.base_context).materialize(c.name for c in b.spec.construction)
    if site['family']=='equal_sides':
        names=list(dict.fromkeys(site['left_edge']+site['right_edge']))
        points=[context[n] for n in names]
        area=abs((points[1].x-points[0].x)*(points[2].y-points[0].y)-(points[1].y-points[0].y)*(points[2].x-points[0].x))/2
        scale=max((a.x-b.x)**2+(a.y-b.y)**2 for a,b in combinations(points,2))
        ratio=area/scale if scale else mp.mpf(0)
        return {'kind':'triangle_area/max_edge_squared','ratio':mp.nstr(ratio,50),'effective':bool(ratio>mp.mpf('1e-8'))}
    points=[v for v in context.values() if isinstance(v,MPPoint)]
    distances=[mp.sqrt((a.x-b.x)**2+(a.y-b.y)**2) for a,b in combinations(points,2)]
    maximum=max(distances,default=mp.mpf(0))
    distance=safe_eval_expr_hp(f'Distance({site["point"]},{site["axis"]})',context)
    ratio=distance/maximum if maximum else mp.mpf(0)
    return {'kind':'distance_to_original_axis_or_center/max_point_distance','ratio':mp.nstr(ratio,50),'effective':bool(ratio>mp.mpf('1e-8'))}


def one(index):
    from mpmath import mp
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.engine.standard.refinement.mpmath_refiner import _run_findroot_closure,_convert_bounds_uncached
    from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
    from geosolver.engine.standard.evaluation.verification_numerics import same_branches
    assert_identity()
    for name,sha in json.loads((OUT/'execution/jacobian-implementation.lock.json').read_text())['files'].items():assert digest(OUT/name)==sha,name
    row=json.loads((RAW/'jacobian-jobs.json').read_text())[index]
    d=RAW/'jacobian'/f'{index:04d}';d.mkdir(exist_ok=True)
    assert not (d/'start.json').exists(),'No refinement retries'
    save(d/'start.json',dict(row,utc=utc()))
    rec=dict(row,status='NA',reason='refinement_failed')
    _,_,_,e=load_case(row['id'],row['arm'])
    # The intervention diagnostic uses the original diagram at these same
    # coordinates, including its unmodified reflected point and only points.
    original_e=e if row['arm']=='original' else load_case(row['id'],'original')[3]
    scales=json.loads((RAW/'jacobian'/f'scaling-{row["id"]}.json').read_text())
    site=next(p['site'] for p in json.loads((OUT/'selection.json').read_text()) if p['id']==row['id'])
    start=time.monotonic()
    try:
        with mp.workdps(80),high_precision_mode():
            x=[mp.mpf(format(float(v),'.17g')) for v in row['x']]
            with capture_selection_trace() as trace_before:e.evaluate_hp_residual(x,precision=80)
            t=time.monotonic()
            with limit(5):
                closed=_run_findroot_closure(evaluator=e,start_point=x,
                     bounds=_convert_bounds_uncached(e.bundle,80),dps=80,
                     target_residual=mp.mpf('1e-24'),max_steps=80,deadline_monotonic=t+5)
            rec['refinement_seconds']=time.monotonic()-t
            if closed is None:save(d/'done.json',rec);return
            y,norm=closed
            with limit(1):
                with capture_selection_trace() as trace_after:hp=e.evaluate_hp_residual(y,precision=80)
                g,viol=e.evaluate_guard(y)
                hard=e.evaluate_hp_hard_feasibility(y,precision=80)
                answer=e.evaluate_answer_hp(y,precision=80)
            if not (hp.is_finite and hp.residual_norm_hp<=mp.mpf('1e-24') and g and hard.hard_feasible and answer.answer_hp is not None and mp.isfinite(answer.answer_hp)):
                rec['reason']='refined_original_conditions_failed';save(d/'done.json',rec);return
            widths=[mp.mpf(format(v,'.17g')) for v in scales['width']]
            rowscales=[mp.mpf(format(v,'.17g')) for v in scales['row_scales']]
            rec.update(refined_x=[mp.nstr(v,90) for v in y],refined_norm=mp.nstr(norm,90),
                       displacement_raw=mp.nstr(mp.sqrt(sum((a-b)**2 for a,b in zip(x,y))),60),
                       displacement_normalized=mp.nstr(mp.sqrt(sum(((a-b)/w)**2 for a,b,w in zip(x,y,widths))),60),
                       branch_change_suspected=not same_branches(tuple(trace_before),tuple(trace_after)))
            try:rec['efficacy']=efficacy(original_e,y,site)
            except Exception as err:rec['efficacy']={'effective':False,'reason':str(err)}
            m,n=len(e.bundle.targets),len(y);steps={}
            for step in ('1e-5','1e-6','1e-7'):
                h=mp.mpf(step);raw=mp.matrix(m,n);normalized=mp.matrix(m,n)
                for j in range(n):
                    plus=y.copy();minus=y.copy();plus[j]+=h*widths[j];minus[j]-=h*widths[j]
                    fp=e.evaluate_hp_residual(plus,precision=80)
                    fm=e.evaluate_hp_residual(minus,precision=80)
                    if not fp.is_finite or not fm.is_finite:raise ValueError('nonfinite_centered_difference')
                    for a in range(m):
                        delta=(fp.residual_vector[a]-fm.residual_vector[a])/(2*h)
                        raw[a,j]=delta/widths[j];normalized[a,j]=delta/rowscales[a]
                rsv=list(mp.svd(raw,compute_uv=False))+[mp.mpf(0)]*max(0,n-m)
                nsv=list(mp.svd(normalized,compute_uv=False))+[mp.mpf(0)]*max(0,n-m)
                def data(v):
                    maximum=max(v,default=mp.mpf(0));minimum=min(v,default=mp.mpf(0))
                    return {'singular_values':[mp.nstr(s,90) for s in v],
                            'sigma_min':mp.nstr(minimum,90),'sigma_max':mp.nstr(maximum,90),
                            'ratio':mp.nstr(minimum/maximum,90) if maximum else None,
                            'rank':sum(s>maximum*mp.mpf('1e-8') for s in v) if maximum else 0}
                steps[step]={'raw':data(rsv),'normalized':data(nsv)}
            rec.update(status='measured',reason=None,m=m,n=n,padded_zero_count=max(0,n-m),steps=steps,
                       structural_deficiency='underdetermined' if n>m else 'not_classified',
                       geometry_singularity_proved=False)
    except MeasurementDeadline:rec['reason']='refinement_or_verification_timeout'
    except Exception as error:rec['reason']=f'{type(error).__name__}: {error}'
    rec['total_seconds']=time.monotonic()-start
    save(d/'done.json',rec)
    print(json.dumps({'index':index,'status':rec['status'],'reason':rec['reason']}),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1].startswith('scale:'):
        index=int(sys.argv[1].split(':')[1])
        cid=json.loads((RAW/'scaling-jobs.json').read_text())[index]
        scaling(cid)
        save(RAW/'scaling'/f'{index:04d}'/'done.json',dict(id=cid,utc=utc()))
    else:one(int(sys.argv[1]))
