"""Q15: deterministic evaluations of frozen endpoints. NO optimization is called."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, itertools, json, math, os, sys, time, traceback
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
os.environ['PYTHONDONTWRITEBYTECODE']='1'
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'jssa/difficulty'))
import numpy as np
from mpmath import mp
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.snapshots import EvaluationStore
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.geometry.mp.mp_core_types import MPPoint, MPCircle
from probe_basins import reference_values

EXPECTED='67124e29d631062bbe046961d8cde84b1f6d100ce2f2c7d3ed9bc790e07f70e0'
VARIANTS={'primary':(1e-6,1e-8,100,True,True,True),
 'strict':(1e-8,1e-10,1000,True,True,True),
 'loose':(1e-4,1e-6,10,True,True,True),
 'no_collinear':(1e-6,1e-8,100,False,True,True),
 'no_radius':(1e-6,1e-8,100,True,False,True),
 'no_scale_probe':(1e-6,1e-8,100,True,True,False),
 'conservative_strict':(1e-8,1e-10,1000,False,True,False)}

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x):return None
    return x

def dump(p,x):
    p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def finite_x(x,n):
    return isinstance(x,list) and len(x)==n and all(isinstance(v,(float,int)) and math.isfinite(v) for v in x)

def no_search(*args,**kwargs):
    raise RuntimeError('Q15 forbids new local searches')

def protect():
    import scipy.optimize as opt
    from geosolver.engine.standard.search import scipy_multistart_backend as smb
    opt.least_squares=opt.minimize=no_search
    smb._collect_local_start_record=smb.least_squares=smb.minimize=no_search

class Figure:
    def __init__(self,bundle,dsl):
        self.store=EvaluationStore(bundle,capacity=16)
        self.all_names=[c['name'] for c in dsl['constructions']]
        excluded={'Line','Circle','Circumcircle','Incircle','Tangent','Ray','Segment','Polygon','Triangle','Vector'}
        self.point_candidates=[c['name'] for c in dsl['constructions'] if c['expression'].split('(')[0].strip() not in excluded]
        self.circle_candidates=[c['name'] for c in dsl['constructions'] if c['expression'].split('(')[0].strip() in {'Circle','Circumcircle','Incircle'}]
        self.cache={}
    def at(self,x):
        key=tuple(x)
        if key in self.cache:return self.cache[key]
        pts={};radii={};types={}
        with mp.workprec(53):
            snap=self.store.get([mp.mpf(float(v)) for v in x],arithmetic='float')
            for name in self.all_names:
                try:
                    value=snap.for_expressions([name])[name]
                    types[name]=type(value).__name__
                    if isinstance(value,MPPoint):
                        a=np.array([float(value.x),float(value.y)])
                        if np.isfinite(a).all():pts[name]=a
                    elif isinstance(value,MPCircle):
                        r=float(value.radius)
                        if math.isfinite(r):radii[name]=abs(r)
                except Exception:pass
        ans=(pts,radii,types)
        self.cache[key]=ans
        return ans

def distances(points,names):
    arr=np.array([points.get(n,[np.nan,np.nan]) for n in names],float).reshape(-1,2)
    dist=np.linalg.norm(arr[:,None,:]-arr[None,:,:],axis=2)
    vals=dist[np.isfinite(dist)]
    diam=float(np.max(vals)) if len(vals) and sum(n in points for n in names)>=2 else math.nan
    return arr,dist,diam

def raw_ratios(pts,names,pairs,triples):
    arr,dist,diam=distances(pts,names)
    pd=np.array([dist[i,j] for i,j in pairs])
    if len(triples):
        a,b,c=arr[triples[:,0]],arr[triples[:,1]],arr[triples[:,2]]
        u,v=b-a,c-a
        ar=np.abs(u[:,0]*v[:,1]-u[:,1]*v[:,0])/2
        sides=np.minimum.reduce([dist[triples[:,0],triples[:,1]],dist[triples[:,0],triples[:,2]],dist[triples[:,1],triples[:,2]]])
    else:ar=sides=np.array([],float)
    if diam>0:return diam,pd/diam,ar/diam**2,sides/diam
    return diam,np.full(len(pairs),np.nan),np.full(len(triples),np.nan),np.full(len(triples),np.nan)

class Diagnostics:
    def __init__(self,pack):
        self.pack=pack
        self.bundle=load_problem_bundle(GeometryProblem.model_validate(pack['case']['dsl']).engine_document())
        self.ev=build_ir_evaluator(self.bundle)
        self.fig=Figure(self.bundle,pack['case']['dsl'])
        self.n=len(self.bundle.var_names)
        box=np.array(pack['box'],float);self.lo=box[:,0];self.hi=box[:,1]
        self.width=self.hi-self.lo;self.mid=(self.lo+self.hi)/2
        self.refs=reference_values(pack['case']['answer'])
        base=[r for r in pack['records'] if r['source']=='raw0']
        starts=[self.fig.at(r['start']) for r in base if finite_x(r.get('start'),self.n)]
        hits=[self.fig.at(r['x']) for r in base if r['cls']=='hit' and finite_x(r.get('x'),self.n)]
        types={k:v for fs in starts+hits for k,v in fs[2].items()}
        self.names=sorted(set(self.fig.point_candidates)-{k for k,v in types.items() if v!='MPPoint'} | {k for fs in starts+hits for k in fs[0]})
        self.circle_names=sorted(set(self.fig.circle_candidates)|{k for fs in starts+hits for k in fs[1]})
        self.pairs=list(itertools.combinations(range(len(self.names)),2))
        self.triples=np.array(list(itertools.combinations(range(len(self.names)),3)),int).reshape(-1,3)
        ds=[];centers=[]
        for pts,_,_ in starts:
            if len(pts)>=2:
                diam=distances(pts,self.names)[2]
                if math.isfinite(diam) and diam>0:
                    ds.append(diam);centers.append(np.mean(list(pts.values()),axis=0))
        self.S0=float(np.median(ds)) if ds else float(np.sqrt(np.mean(self.width**2)))
        self.O0=np.median(centers,axis=0) if centers else np.zeros(2)
        self.scale_fallback=not bool(ds)
        refs=hits if hits else starts
        self.mask_p=np.ones(len(self.pairs),bool);self.mask_t=np.ones(len(self.triples),bool)
        for pts,_,_ in refs:
            _,pd,ar,_=raw_ratios(pts,self.names,self.pairs,self.triples)
            self.mask_p &= np.isfinite(pd)&(pd<=1e-4)
            self.mask_t &= np.isfinite(ar)&(ar<=1e-6)
        if not refs:self.mask_p[:]=False;self.mask_t[:]=False
        self.hits=hits;self.starts=starts
        self.base_meta={'n_vars':self.n,'n_points':len(self.names),'n_circles':len(self.circle_names),
            'names':self.names,'circle_names':self.circle_names,'S0':self.S0,'O0':self.O0.tolist(),
            'initial_figures':len(ds),'scale_fallback':self.scale_fallback,'hit_figures':len(hits),
            'mask_reference':'hits' if hits else 'starts_only',
            'pairs_total':len(self.pairs),'pairs_excluded':int(sum(self.mask_p)),
            'triples_total':len(self.triples),'triples_excluded':int(sum(self.mask_t))}
        self.eq_cache={};self.hard_cache={};self.metric_cache={};self.boundary_cache={}
    def eq(self,x):
        key=tuple(x)
        if key not in self.eq_cache:
            try:
                r=self.ev.evaluate_float_residual(list(x));v=np.asarray(r.residual_vector,float)
                self.eq_cache[key]=float(np.linalg.norm(v)) if r.is_finite and np.isfinite(v).all() else math.nan
            except Exception:self.eq_cache[key]=math.nan
        return self.eq_cache[key]
    def hard(self,x):
        key=tuple(x)
        if key not in self.hard_cache:
            try:self.hard_cache[key]=bool(self.ev.evaluate_float_hard_feasibility(list(x),include_margins=False).hard_feasible)
            except Exception:self.hard_cache[key]=None
        return self.hard_cache[key]
    def geometry(self,x):
        pts,radii,_=self.fig.at(x)
        diam,pd,ar,sides=raw_ratios(pts,self.names,self.pairs,self.triples)
        pd[self.mask_p]=np.nan;ar[self.mask_t]=np.nan
        ar[sides<1e-3]=np.nan
        def mn(vals):
            good=np.flatnonzero(np.isfinite(vals))
            if not len(good):return math.nan,None
            j=good[np.argmin(vals[good])];return float(vals[j]),int(j)
        pair,j=mn(pd);area,k=mn(ar)
        rad=max((float(np.linalg.norm(p-self.O0)) for p in pts.values()),default=math.nan)
        cr=min(radii.values(),default=math.nan)/diam if diam>0 else math.nan
        return {'diameter':diam,'pair_ratio':pair,'area_ratio':area,'radius_ratio':cr,
            'diameter_over_S0':diam/self.S0 if self.S0>0 else math.nan,
            'escape_ratio':rad/self.S0 if self.S0>0 else math.nan,
            'pair':','.join(self.names[i] for i in self.pairs[j]) if j is not None else '',
            'triple':','.join(self.names[i] for i in self.triples[k]) if k is not None else '',
            'n_points_defined':len(pts),'n_circles_defined':len(radii),
            'geometry_complete':len(pts)==len(self.names) and len(radii)==len(self.circle_names) and len(pts)>=2}
    def metrics(self,x):
        key=tuple(x)
        if key in self.metric_cache:return self.metric_cache[key].copy()
        out=self.geometry(x);out['residual']=self.eq(x);out['hard_feasible']=self.hard(x)
        arr=np.array(x,float)
        out['inside_box']=bool(np.all((arr>=self.lo)&(arr<=self.hi)))
        out['scale_probe']=False;out['scale_probe_evaluations']=0;out['scale_probe_finite']=True
        f=out['residual'];prev=f;factors=[]
        # Short-circuit a failed condition: equivalent to evaluating all four fixed points.
        if math.isfinite(f) and f>1e-12:
            for t in (2,4,8):
                xx=self.mid+t*(arr-self.mid);v=self.eq(xx)
                out['scale_probe_evaluations']+=1;factors.append(v)
                if not math.isfinite(v):out['scale_probe_finite']=False;break
                if not v<=prev*(1-1e-6):break
                prev=v
            if len(factors)==3 and all(math.isfinite(v) for v in factors) and all(b<=a*(1-1e-6) for a,b in zip([f]+factors,factors)) and factors[-1]<=0.5*f:
                final=self.geometry((self.mid+8*(arr-self.mid)).tolist())
                out['scale_radius_growth']=final['escape_ratio']/out['escape_ratio'] if out['escape_ratio']>0 else math.nan
                out['scale_probe']=bool(out['scale_radius_growth']>=4)
        out['scale_residuals']=factors
        self.metric_cache[key]=out.copy()
        return out
    def boundary(self,x,k,old):
        if old and old.get('end_feasible') is True and 'b6' in old:
            return bool(old['b6']),'G_saved_b6'
        key=(tuple(x),k)
        if key in self.boundary_cache:return self.boundary_cache[key]
        rng=np.random.default_rng([15023,self.pack['index'],int(k or 0)])
        rand=rng.normal(size=(8,self.n));norm=np.linalg.norm(rand,axis=1)
        rand=rand/np.maximum(norm[:,None],1e-300)
        dirs=itertools.chain(np.eye(self.n),-np.eye(self.n),rand)
        unknown=False
        for v in dirs:
            h=self.hard(np.array(x)+1e-6*self.width*v)
            if h is False:
                result=(True,'fixed_axes_and_random');break
            if h is None:unknown=True
        else:result=(None if unknown else False,'fixed_axes_and_random')
        self.boundary_cache[key]=result
        return result
    def branch(self,x,metrics):
        out={'d':False,'d_unconfirmed':False,'recomputed_hit':False}
        if not(math.isfinite(metrics['residual']) and metrics['residual']<=1e-8 and metrics['hard_feasible'] and metrics['inside_box']):return out
        try:
            guard,tags=self.ev.evaluate_guard(x)
            if not guard:return out
            with mp.workdps(50),high_precision_mode():
                xx=[mp.mpf(repr(float(v))) for v in x]
                ans=self.ev.evaluate_answer_hp(xx,precision=50).answer_hp
                if ans is None or not mp.isfinite(ans) or abs(mp.im(ans))>mp.mpf('1e-30'):return out
                value=mp.re(ans)
                hit=any(abs(value-mp.mpf(repr(v)))<=mp.mpf('1e-6')*max(1,abs(mp.mpf(repr(v)))) for v in self.refs)
                if not hit:
                    res=self.ev.evaluate_hp_residual(xx,precision=50)
                    hp=self.ev.evaluate_hp_hard_feasibility(xx,precision=50,include_margins=False)
                    hg,_=self.ev.evaluate_guard(xx)
                    verified=bool(res.is_finite and res.residual_norm_hp<=mp.mpf('1e-10') and hp.hard_feasible and hg)
            # Serialization is deliberately outside high_precision_mode.
            out['answer_recomputed']=float(value)
            out['recomputed_hit']=bool(hit)
            if not hit:
                out.update(hp_residual=float(res.residual_norm_hp),hp_hard=bool(hp.hard_feasible),
                           hp_guard=bool(hg),d=verified,d_unconfirmed=not verified)
        except Exception as exc:out['branch_error']=type(exc).__name__
        return out

def le(x,t):return isinstance(x,(float,int)) and math.isfinite(x) and x<=t

def label(row,variant='primary'):
    if not row.get('finite_x'):return {'a':False,'b':False,'c':False,'d':False,'e':False,'ab':False,'vote':'unknown'}
    dist,area,escape,flat,radius,scale=VARIANTS[variant]
    a=bool(le(row.get('pair_ratio'),dist) or (flat and le(row.get('area_ratio'),area)) or
           (radius and le(row.get('radius_ratio'),dist)) or le(row.get('diameter_over_S0'),dist))
    b=bool(row.get('escape_ratio',-1)>=escape or (scale and row.get('scale_probe',False)))
    c=bool(row.get('c',False))
    d=bool(row.get('branch_verified',False) and not(a or b))
    e=bool(not(a or b or c or d) and row.get('measurement_complete',False))
    vote=next((nm for nm,val in [('b',b),('a',a),('c',c),('d',d),('e',e)] if val),'unknown')
    return dict(a=a,b=b,c=c,d=d,e=e,ab=a or b,vote=vote)

def run_case(task):
    pathstr,force=task
    protect();t0=time.monotonic();path=Path(pathstr)
    pack=json.loads(gzip.decompress(path.read_bytes()));cid=pack['id']
    outdir=HERE/'classified';outdir.mkdir(exist_ok=True)
    summarypath=outdir/(cid+'.json')
    if summarypath.exists() and not force:return json.loads(summarypath.read_text())
    stats=defaultdict(Counter);variants={v:defaultdict(Counter) for v in VARIANTS};rows=[]
    try:
        d=Diagnostics(pack);meta=d.base_meta;errors=Counter()
        for r in pack['records']:
            key=r['source']+'/'+r['arm'];st=stats[key];st['records']+=1
            st['cls_'+r['cls']]+=1
            if r['cls']=='hit':st['hit']+=1;continue
            st['failed_records']+=1
            row={k:r.get(k) for k in ('source','arm','k','cls','res','ans','native_joint','native_joint_scope') if k in r}
            row['id']=cid;row['finite_x']=finite_x(r.get('x'),d.n)
            if row['finite_x']:
                st['finite_failed']+=1
                try:
                    row.update(d.metrics(r['x']))
                    row['c']=False
                    if row['hard_feasible'] is True and math.isfinite(row['residual']) and row['residual']>1e-8:
                        row['c'],row['c_source']=d.boundary(r['x'],r.get('k'),pack['G_diagnostics'].get(str(r['k'])) if r['source']=='raw0' else None)
                    row['measurement_complete']=bool(row['geometry_complete'] and math.isfinite(row['residual']) and row['hard_feasible'] is not None and row['c'] is not None)
                    pre=label(row)
                    # Evaluate candidate branch at the original saved point, never refine it.
                    if not(pre['a'] or pre['b']):
                        branch=d.branch(r['x'],row);row.update(branch);row['branch_verified']=branch['d']
                    row.update(label(row))
                except Exception as exc:
                    row['evaluation_error']=repr(exc);row['measurement_complete']=False
                    errors[type(exc).__name__]+=1;row.update(label(row))
            else:row.update(label(row))
            for v in VARIANTS:
                labels=label(row,v);ct=variants[v][key]
                ct['failed_records']+=1;ct['finite_failed']+=row['finite_x']
                ct['vote_'+labels['vote']]+=1
                for flag in 'abcde':ct[flag]+=labels[flag]
                ct['ab']+=labels['ab']
                if labels['a'] and labels['b']:ct['a_and_b']+=1
                ct['pattern_'+''.join(f for f in 'abcd' if labels[f])]+=1
            for flag in ('geometry_complete','measurement_complete','scale_probe','d_unconfirmed','recomputed_hit'):
                st[flag]+=bool(row.get(flag))
            st['native_joint_positive']+=bool(row.get('native_joint',0)>0)
            st['res_le_1e8']+=le(row.get('residual'),1e-8)
            st['scale_probe_evaluations']+=row.get('scale_probe_evaluations',0)
            rows.append(row)
        # Positive control is descriptive only; masks were learned from these hit figures.
        hit_control=Counter()
        for r in pack['records']:
            if r['source']=='raw0' and r['cls']=='hit' and finite_x(r.get('x'),d.n):
                rr={'finite_x':True,**d.geometry(r['x'])}
                ll=label(rr);hit_control['n']+=1
                for f in ('a','b','ab'):hit_control[f]+=ll[f]
        result={'id':cid,'status':'ok','seconds':time.monotonic()-t0,'meta':meta,
            'source_stats':stats,'variants':variants,'human':pack.get('human',{}),
            'basins':pack.get('basins',{}),'hit_control':hit_control,'errors':errors}
    except Exception as exc:
        result={'id':cid,'status':'error','error':repr(exc),'traceback':traceback.format_exc(),'seconds':time.monotonic()-t0}
    data=''.join(json.dumps(clean(r),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n' for r in rows).encode()
    (outdir/(cid+'.jsonl.gz')).write_bytes(gzip.compress(data,mtime=0))
    dump(summarypath,result)
    return clean(result)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);ap.add_argument('--ids',nargs='*');ap.add_argument('--force',action='store_true');ap.add_argument('--ids-file',type=Path);args=ap.parse_args()
    assert 1<=args.workers<=4
    assert hashlib.sha256((HERE/'preregistration.md').read_bytes()).hexdigest()==EXPECTED
    manifest=json.loads((HERE/'input-manifest.json').read_text())
    paths=sorted((HERE/'inputs').glob('*.gz'))
    if args.ids_file:args.ids=args.ids_file.read_text().splitlines()
    if args.ids:paths=[p for p in paths if p.name[:-8] in args.ids]
    for p in paths:assert hashlib.sha256(p.read_bytes()).hexdigest()==manifest['snapshots'][p.name]
    start=time.monotonic()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs={pool.submit(run_case,(str(p),args.force)):p for p in paths}
        for i,f in enumerate(as_completed(futs),1):
            r=f.result()
            print(json.dumps({'done':i,'total':len(paths),'id':r['id'],'status':r['status'],'seconds':round(r['seconds'],2),'elapsed':round(time.monotonic()-start,2),'error':r.get('error')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
