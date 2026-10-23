"""Frozen small input perturbation checks; no random/multistart search."""
from __future__ import annotations
import copy
import hashlib
import json
import signal
import time
import numpy as np
from mpmath import mp
from scipy.optimize import least_squares
from measure import HERE, ROOT, make_evaluator, eval_ft, raw_f, clean, write_json

PARAMETERS={
    'AIME-2006-I-01':['AB','BC','CD'],
    'AIME-2006-I-07':['area_ratio','illustrative_angle'],
    'AIME-2006-II-01':['area'],
}


def changed(dsl, parameter, eta):
    d=copy.deepcopy(dsl)
    k=repr(1+float(eta))
    byname={x['name']:x for x in d['constructions']}
    if d['id']=='AIME-2006-I-01':
        a=f'(18*({k}))' if parameter=='AB' else '18'
        b=f'(21*({k}))' if parameter=='BC' else '21'
        c=f'(14*({k}))' if parameter=='CD' else '14'
        byname['B']['expression']=f'Point({a},0)'
        byname['C']['expression']=f'Point({a},{b})'
        for cond in d['conditions']:
            if cond.get('left') in ('Distance(A, B)','Dx'):
                cond['right']=a
            if cond.get('left') in ('Distance(B, C)','Dy'):
                cond['right']=b
            if cond.get('left')=='Distance(C, D)':
                cond['right']=c
    elif d['id']=='AIME-2006-I-07':
        if parameter=='area_ratio':
            d['conditions'][0]['right']=f'11*({k})*Breg/5'
        else:
            s=byname['C0']['expression']
            assert s.count('10 * pi')==2
            byname['C0']['expression']=s.replace('10 * pi',f'(10*({k})) * pi')
    elif d['id']=='AIME-2006-II-01':
        assert parameter=='area'
        d['conditions'][10]['right']=f'2116*({k})*(sqrt(2)+1)'
    else:
        raise ValueError(d['id'])
    return d


def alarm(signum,frame):
    raise TimeoutError('5 second local solve budget')


def main():
    lock={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('perturbation-plan.md','perturb.py','protocol.md','measurements.json')}
    write_json('perturbation-lock.json',{'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'hashes':lock})
    cases={c['id']:c for c in (json.loads(s) for s in (ROOT/'benchmarks/cases.jsonl').read_text().splitlines())}
    measures={r['id']:r for r in json.loads((HERE/'measurements.json').read_text())}
    selected=json.loads((HERE/'selected-controls.json').read_text())
    assert selected==list(PARAMETERS)
    signal.signal(signal.SIGALRM,alarm)
    tstart=time.monotonic()
    runs=[]; sensitivities=[]; directional=[]
    for cid in selected:
        r=measures[cid];dsl=cases[cid]['dsl']
        x=np.asarray(r['x']);D=np.asarray(r['scales']);w=np.asarray(r['row_weights']);J=np.asarray(r['jacobian']);g=np.asarray(r['gradient']);T=max(1,abs(r['target']))
        A=w[:,None]*J
        pinv=np.linalg.pinv(A,rcond=1e-12)
        b0,e0=make_evaluator(dsl); f0,t0=eval_ft(b0,e0,x)
        for dname, direction in [('weak',np.asarray(r['main']['weak_direction'])),('gradient',g/np.linalg.norm(g))]:
            for h in (1e-3,1e-4,1e-5):
                fp,tp=eval_ft(b0,e0,x+h*D*direction)
                fm,tm=eval_ft(b0,e0,x-h*D*direction)
                pred_t=float(g@direction); obs_t=(tp-tm)/(2*h)
                pred_f=A@direction; obs_f=w*(fp-fm)/(2*h)
                directional.append({'id':cid,'direction':dname,'h':h,'target_derivative_predicted':pred_t,
                                    'target_derivative_observed':obs_t,'target_relative_error':abs(pred_t-obs_t)/max(abs(pred_t),1e-8),
                                    'residual_derivative_relative_error':np.linalg.norm(pred_f-obs_f)/max(np.linalg.norm(pred_f),1e-8)})
        for param in PARAMETERS[cid]:
            ep=[]
            for eta in (-1e-6,1e-6):
                bp,ev=make_evaluator(changed(dsl,param,eta))
                ep.append(eval_ft(bp,ev,x))
            B=(ep[1][0]-ep[0][0])/(2e-6); direct=(ep[1][1]-ep[0][1])/(2e-6)
            v=-pinv@(w*B)
            dt=direct+g@v
            compat=np.linalg.norm(A@v+w*B)/max(np.linalg.norm(w*B),1e-15)
            s={'id':cid,'parameter':param,'role':('illustrative_parameter_not_verified_original_given' if param=='illustrative_angle' else 'explicit_DSL_given'),
               'normalized_coordinate_gain':np.linalg.norm(v),'relative_target_gain':abs(dt)/T,'target_derivative':dt,
               'direct_target_derivative':direct,'indirect_target_derivative':g@v,'coordinate_derivative_scaled':v,
               'compatibility_relative_error':compat,'fits':[]}
            for h in (1e-4,1e-5):
                pair=[]
                for eta in (-h,h):
                    d=changed(dsl,param,eta)
                    bp,ev=make_evaluator(d)
                    run={'id':cid,'parameter':param,'eta':eta,'dsl_sha256':hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()}
                    ts=time.monotonic()
                    signal.alarm(5)
                    try:
                        opt=least_squares(lambda z:w*eval_ft(bp,ev,x+D*z)[0],np.zeros(len(x)),method='trf',max_nfev=100,xtol=1e-12,ftol=1e-12,gtol=1e-12)
                        xx=x+D*opt.x
                        fnew,tnew=eval_ft(bp,ev,xx)
                        fr=raw_f(ev,xx)
                        hard=bool(ev.evaluate_float_hard_feasibility(xx.tolist(),include_margins=False).hard_feasible)
                        guard=bool(ev.evaluate_guard(xx.tolist())[0])
                        ok=bool(np.max(np.abs(fr),initial=0)<=1e-8 and hard and guard)
                        run.update(x=xx,target=tnew,raw_residual_max=np.max(np.abs(fr),initial=0),hard=hard,guard=guard,ok=ok,nfev=opt.nfev,optimizer_status=int(opt.status))
                        pair.append((opt.x,tnew,ok))
                    except Exception as exc:
                        run.update(ok=False,error=type(exc).__name__+': '+str(exc))
                        pair.append(None)
                    finally:
                        signal.alarm(0)
                    run['elapsed_s']=time.monotonic()-ts
                    runs.append(run)
                if all(p is not None and p[2] for p in pair):
                    dv=(pair[1][0]-pair[0][0])/(2*h)
                    dtt=(pair[1][1]-pair[0][1])/(2*h)
                    ve=np.linalg.norm(dv-v)/max(np.linalg.norm(v),1e-8)
                    te=abs((dtt-dt)/T)/max(abs(dt/T),1e-8)
                    s['fits'].append({'h':h,'coordinate_gain_observed':np.linalg.norm(dv),'target_gain_observed':abs(dtt)/T,
                                      'coordinate_check_error':ve,'target_check_error':te,
                                      'coordinate_error_absolute':np.linalg.norm(dv-v),'target_error_absolute':abs((dtt-dt)/T),
                                      'coordinate_derivative_observed':dv,'target_derivative_observed':dtt,
                                      'check_pass':bool((ve<=.01 or np.linalg.norm(dv-v)<=1e-8) and (te<=.01 or abs((dtt-dt)/T)<=1e-8))})
                else:
                    s['fits'].append({'h':h,'check_pass':False,'reason':'a solve did not meet original residual/guard/hard criterion'})
            sensitivities.append(s)
    # Elementary counterexample, independent of the solver and explicitly so labelled.
    triangles=[]
    with mp.workdps(70):
        for m in (2,10,100):
            a=mp.mpf(m*m+1);c=mp.mpf(2*(m*m-1));height=mp.mpf(2*m)
            eps=mp.mpf('1e-10')
            H=lambda aa:mp.sqrt(aa*aa-c*c/4)
            derivative=(H(a*(1+eps))-H(a*(1-eps)))/(2*eps)/height
            theory=a*a/(4*m*m)
            triangles.append({'m':m,'equal_side':str(a),'base':str(c),'height':str(height),'area':str(c*height/2),
                              'relative_height_condition_theory':str(theory),'central_difference':str(derivative),
                              'relative_difference':str(abs(derivative-theory)/theory)})
    write_json('perturbation-runs.json',runs)
    write_json('input-sensitivities.json',sensitivities)
    write_json('directional-checks.json',directional)
    write_json('integer-triangles.json',triangles)
    summary={'elapsed_s':time.monotonic()-tstart,'n_runs':len(runs),'solves_original_checks_pass':sum(r['ok'] for r in runs),
             'n_parameter_groups':len(sensitivities),'finite_difference_checks_pass':sum(f['check_pass'] for s in sensitivities for f in s['fits']),
             'n_finite_difference_checks':sum(len(s['fits']) for s in sensitivities),
             'max_directional_target_error':max(d['target_relative_error'] for d in directional),
             'max_directional_residual_error':max(d['residual_derivative_relative_error'] for d in directional),
             'plan_and_script_unchanged':all(hashlib.sha256((HERE/name).read_bytes()).hexdigest()==v for name,v in lock.items())}
    write_json('perturbation-summary.json',summary)
    print(json.dumps(clean({'summary':summary,'input_sensitivities':sensitivities,'triangles':triangles}),indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
