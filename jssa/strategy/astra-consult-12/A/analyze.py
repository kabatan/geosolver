"""Compare a completed solver-free feature file with existing outcomes.

No geometry solve is run. scipy.optimize is used ONLY for small statistical
prediction models. Every output is confined to this directory.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import rankdata, spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def number(x):
    try:
        return float(x)
    except (ValueError,TypeError):
        return float("nan")


def json_safe(value):
    if isinstance(value,dict):
        return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value,list):
        return [json_safe(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):
        return None
    return value


def corr(x,y):
    if len(x)<3 or np.ptp(x)==0 or np.ptp(y)==0:
        return float("nan")
    return float(spearmanr(x,y).statistic)


def residual_rank(x,groups):
    r = rankdata(x)
    for g in np.unique(groups):
        select=groups==g
        r[select]-=np.mean(r[select])
    return r


def partial(x,y,g):
    a,b=residual_rank(x,g),residual_rank(y,g)
    if np.std(a)==0 or np.std(b)==0:
        return float("nan")
    return float(np.corrcoef(a,b)[0,1])


def association(rows,xkey,ykey,adjust=False,permutations=0):
    rows=[r for r in rows if math.isfinite(number(r.get(xkey))) and math.isfinite(number(r.get(ykey)))]
    x=np.array([number(r[xkey]) for r in rows])
    y=np.array([number(r[ykey]) for r in rows])
    groups=np.minimum(5,np.array([int(r['n_vars']) for r in rows]))
    fn=(lambda ix: partial(x[ix],y[ix],groups[ix])) if adjust else (lambda ix:corr(x[ix],y[ix]))
    est=fn(np.arange(len(rows)))
    rng=np.random.default_rng(20261023)
    bs=[fn(rng.integers(0,len(rows),len(rows))) for _ in range(2000)] if len(rows)>=3 else []
    bs=np.asarray(bs); bs=bs[np.isfinite(bs)]
    out={'n':len(rows),'rho':est,'ci95':np.quantile(bs,[.025,.975]).tolist() if len(bs) else None}
    if permutations:
        xr,yr=residual_rank(x,groups),residual_rank(y,groups)
        den=np.linalg.norm(xr)*np.linalg.norm(yr)
        base=float(np.dot(xr,yr)/den)
        strata=[np.flatnonzero(groups==g) for g in np.unique(groups)]
        count=0
        for _ in range(permutations):
            xp=xr.copy()
            for ix in strata:
                xp[ix]=rng.permutation(xr[ix])
            count+=np.dot(xp,yr)/den<=base
        out['negative_direction_permutation_p']=(count+1)/(permutations+1)
    return out


def design(train,test,features):
    ntrain,ntest=len(train),len(test)
    a=[np.ones(ntrain)];b=[np.ones(ntest)]
    if 'n_vars' in features:
        for g in [2,3,4,5]:
            a.append(np.array([min(5,int(r['n_vars']))==g for r in train],float))
            b.append(np.array([min(5,int(r['n_vars']))==g for r in test],float))
    if 'contest' in features:
        for c in sorted(set(r['contest'] for r in train))[1:]:
            a.append(np.array([r['contest']==c for r in train],float))
            b.append(np.array([r['contest']==c for r in test],float))
    if 'human' in features:
        # Percentile mappings are learned from training problems only.
        vals={c:np.array([float(r['human']) for r in train if r['contest']==c])
              for c in set(r['contest'] for r in train)}
        def value(row):
            v=vals.get(row['contest'],np.array([float(r['human']) for r in train]))
            x=float(row['human'])
            return (np.sum(v<x)+.5*np.sum(v==x))/len(v)
        a.append(np.array([value(r) for r in train]));b.append(np.array([value(r) for r in test]))
    if 'A' in features:
        a.append(np.array([float(r['A']) for r in train]));b.append(np.array([float(r['A']) for r in test]))
    a,b=np.column_stack(a),np.column_stack(b)
    if a.shape[1]>1:
        mean=a[:,1:].mean(axis=0);std=a[:,1:].std(axis=0)
        std[std<1e-12]=1.
        a[:,1:]=(a[:,1:]-mean)/std;b[:,1:]=(b[:,1:]-mean)/std
    return a,b


def predict(train,test,features):
    x,xt=design(train,test,features)
    y=np.array([float(r['p']) for r in train])
    # Fixed, outcome-independent ridge strength; equal weight per problem.
    ridge=0.01
    def objective(beta):
        eta=x@beta
        loss=np.mean(np.logaddexp(0.,eta)-y*eta)+ridge*np.sum(beta[1:]**2)/2
        grad=x.T@(expit(eta)-y)/len(y)
        grad[1:]+=ridge*beta[1:]
        return loss,grad
    fit=minimize(objective,np.zeros(x.shape[1]),jac=True,method='L-BFGS-B',
                 options={'maxiter':500,'maxls':50,'ftol':1e-12,'gtol':1e-9})
    # A line search may report roundoff after the convex objective has already
    # reached stationarity. Check the gradient rather than the message alone.
    grad_norm=float(np.max(np.abs(objective(fit.x)[1])))
    if not fit.success and grad_norm>1e-7:
        raise RuntimeError(f'Prediction regression did not converge: {fit.message}')
    return expit(xt@fit.x)


def cross_validation(rows,models,label):
    n=len(rows); y=np.array([float(r['p']) for r in rows])
    pred={name:np.empty((10,n)) for name in models}
    for rep in range(10):
        ix=np.random.default_rng(20261023+rep).permutation(n)
        for fold in np.array_split(ix,5):
            train=np.setdiff1d(np.arange(n),fold)
            for name,features in models.items():
                pred[name][rep,fold]=predict([rows[j] for j in train],[rows[j] for j in fold],features)
    summary={'n':n,'models':{},'differences':{}}
    losses={}
    for name,p in pred.items():
        p=np.clip(p,1e-8,1-1e-8)
        loss=-(y*np.log(p)+(1-y)*np.log1p(-p))
        losses[name]=loss.mean(axis=0)
        summary['models'][name]={'log_loss':float(loss.mean()),
                                 'rmse':float(np.sqrt(((p-y)**2).mean())),
                                 'repeat_log_loss_sd':float(loss.mean(axis=1).std(ddof=1))}
    for base,added in [('n_vars','n_vars+A'),('n_vars+human','n_vars+human+A')]:
        if base not in losses or added not in losses:
            continue
        diff=losses[added]-losses[base]
        rng=np.random.default_rng(20261023)
        means=np.array([np.mean(diff[rng.integers(0,n,n)]) for _ in range(2000)])
        summary['differences'][f'{added} minus {base}']={
            'delta_log_loss':float(diff.mean()),'descriptive_problem_bootstrap_ci95':np.quantile(means,[.025,.975]).tolist()}
    with (HERE/f'cv-{label}.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['id','p',*pred]);w.writeheader()
        for i,r in enumerate(rows):
            w.writerow({'id':r['id'],'p':r['p'],**{k:float(v[:,i].mean()) for k,v in pred.items()}})
    return summary


def main():
    features=read_csv(HERE/'attraction.csv')
    assert len(features)==292,'Finish measurement before looking at the correlations.'
    basins=read_csv(ROOT/'jssa/difficulty/minima/basins-323.csv')
    basins={r['id']:r for r in basins if int(r['n_vars'] or 0)>0}
    human={r['case_id']:r for r in read_csv(ROOT/'jssa/difficulty/ghost-1023/human_feat.csv')}
    endpoints=read_csv(ROOT/'jssa/difficulty/ghost-1023/endpoints_v1.csv')
    failures=defaultdict(list)
    for r in endpoints:
        if r['cls']!='hit' and math.isfinite(number(r['coinc'])):
            failures[r['id']].append(number(r['coinc'])<1e-4)
    fg={cid:float(np.mean(a)) for cid,a in failures.items() if len(a)>=5}
    rows=[]
    for f in features:
        r={**basins[f['id']],**f}
        for k in ['n_vars','n_starts']:
            r[k]=int(basins[f['id']][k])
        for k in ['p','A','A_tau003','A_tau03','coverage','frac_near']:
            r[k]=number(r.get(k))
        hr=human.get(r['id'],{})
        r.update(human=number(hr.get('human')),contest=hr.get('contest','unknown'),
                 f_ghost=fg.get(r['id'],float('nan')))
        rows.append(r)
    valid=[r for r in rows if r['status']=='ok' and math.isfinite(r['A'])]
    hs=[r for r in valid if math.isfinite(r['human'])]
    # Descriptive human ranks use all available members of this same population.
    for group in [rows,valid,hs]:
        for c in set(r['contest'] for r in group):
            sub=[r for r in group if r['contest']==c and math.isfinite(r['human'])]
            for r,v in zip(sub,rankdata([r['human'] for r in sub])/max(1,len(sub))):
                r['human_rank']=float(v)
    report={
        'status_counts':dict(Counter(r['status'] for r in rows)),
        'elapsed_sum_sec':sum(number(r.get('elapsed_sec')) for r in rows if math.isfinite(number(r.get('elapsed_sec')))),
        'eligible':len(valid),'human_eligible':len(hs),'A_zero_count':sum(r['A']==0 for r in valid),
        'A_quantiles':np.quantile([r['A'] for r in valid],[0,.25,.5,.75,1]).tolist(),
        'primary':association(valid,'A','p'),
        'primary_adjust_n':association(valid,'A','p',True,10000),
        'n_vars_p_eligible':association(valid,'n_vars','p'),
        'n_vars_p_all':association(rows,'n_vars','p'),
        'n_vars_p_endpoint_subset':association([r for r in rows if math.isfinite(r['f_ghost'])],'n_vars','p'),
        'A_n_vars':association(valid,'A','n_vars'),
        'A_f_ghost':association(valid,'A','f_ghost'),
        'reproduce_f_ghost_p':association(rows,'f_ghost','p'),
        'reproduce_f_ghost_human':association(rows,'f_ghost','human'),
        'human':{
            'A_p':association(hs,'A','p'),
            'n_vars_p':association(hs,'n_vars','p'),
            'human_rank_p':association(hs,'human_rank','p'),
            'A_human_rank':association(hs,'A','human_rank'),
        },
        'sensitivity':{
            'tau003':association(valid,'A_tau003','p'),
            'tau03':association(valid,'A_tau03','p'),
            'starts_ge100':association([r for r in valid if r['n_starts']>=100],'A','p'),
            'coverage1':association([r for r in valid if r['coverage']==1],'A','p'),
        },
        'strata':{},'halves':{},
    }
    for g in range(1,6):
        sub=[r for r in valid if min(5,r['n_vars'])==g]
        report['strata'][str(g)]={'n':len(sub),'rho':corr([r['A'] for r in sub],[r['p'] for r in sub])}
    ordered=sorted(valid,key=lambda r:(r['A'],r['id']))
    for name,sub in [('lower',ordered[:len(ordered)//2]),('upper',ordered[len(ordered)//2:])]:
        report['halves'][name]={'n':len(sub),'median_A':float(np.median([r['A'] for r in sub])),
                               'median_p':float(np.median([r['p'] for r in sub])),
                               'mean_p':float(np.mean([r['p'] for r in sub]))}
    report['cv_all']=cross_validation(valid,{'intercept':[],'n_vars':['n_vars'],
                                            'A':['A'],'n_vars+A':['n_vars','A']},'all')
    report['cv_human']=cross_validation(hs,{
        'contest':['contest'],'n_vars':['contest','n_vars'],'human':['contest','human'],
        'A':['contest','A'],'n_vars+A':['contest','n_vars','A'],
        'n_vars+human':['contest','n_vars','human'],
        'n_vars+human+A':['contest','n_vars','human','A']},'human')
    report['examples']=[{k:r[k] for k in ['id','n_vars','A','p','coverage','f_ghost']}
                        for r in sorted(valid,key=lambda r:r['A'],reverse=True)[:10]]
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (HERE/'joined.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    (HERE/'analysis.json').write_text(json.dumps(json_safe(report),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps(json_safe(report),indent=2,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
