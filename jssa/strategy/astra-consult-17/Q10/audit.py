"""Post-comparison real-branch audit. Hand-derived charts, NOT blind discovery.

Imports and writes stay in Q10; H and local git refs are read-only sources.
"""
from pathlib import Path
import sys,os,json,subprocess,hashlib,time,itertools
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE/'vendor'));sys.path.insert(0,str(HERE))
import sympy as sp
from certificate import Prover,make_certificate,isolate,deadline
from l_certificate import sparse
from verify_certificate import verify
T=sp.Symbol('T')
OUT=HERE/'audit';OUT.mkdir(exist_ok=True)
CHART=OUT/'charts';CHART.mkdir(exist_ok=True)
def save(path,obj):
    raw=json.dumps(obj,indent=2,ensure_ascii=False,default=str)+'\n'
    assert len(raw.encode())<16*1024**2
    path.write_text(raw)

def identity(cid,vs,fs,q,cofs=None,s=sp.Integer(1),N=0,reason='',origin='Q10 hand-derived'):
    vs=list(vs);fs=list(map(sp.sympify,fs));s=sp.sympify(s);q=sp.sympify(q)
    start=time.perf_counter()
    if cofs is None:
        assert s==1 and N==0
        with deadline(30):
            pr=Prover(fs,vs,order='grevlex');cofs=pr.coefficients(q)
        assert cofs is not None,cid
    cofs=list(map(sp.sympify,cofs))
    assert sp.expand(s**N*q-sum(c*f for c,f in zip(cofs,fs)))==0,cid
    cert={'variables':list(map(str,vs)),'N':N,'s':sparse(s,vs),'Q':sparse(q,vs),
          'F':[sparse(f,vs) for f in fs],'C':[sparse(c,vs) for c in cofs],
          'id':cid,'Q_expression':str(q),'system_kind':'human-derived real chart; not original fresh ideal',
          'origin':origin,'nonzero_reason':reason,'equations':list(map(str,fs)),
          'cofactor_expressions':list(map(str,cofs)),'s_expression':str(s)}
    assert verify(cert)
    cert['exact_check_seconds']=time.perf_counter()-start
    bounds=(-sp.Integer(1),sp.Integer(1),False,False) if cid=='aime-2003-1-12' else (sp.Integer(0),sp.oo,False,False)
    cert['root_check']=isolate(q,T,bounds)
    assert cert['root_check']['unique'],cid
    save(CHART/f'{cid}.json',cert)
    return dict(id=cid,Q=str(q),unique=True,origin=origin,bytes=(CHART/f'{cid}.json').stat().st_size)

def copy_history():
    p=OUT/'legacy';p.mkdir(exist_ok=True);manifest=[]
    ref='origin/claude/project-thread-ulho54'
    cases=[('out',c) for c in ['AIME-2015-II-07','HMMT-2008-FEB-GEO-06','HMMT-2013-FEB-GEO-02','HMMT-2013-FEB-GEO-08','HMMT-2022-FEB-GEO-01']]+[('out_nd','aime-2000-2-6')]
    for folder,cid in cases:
        dest=p/cid;dest.mkdir(exist_ok=True)
        for name in ['system.txt','certificate.txt','result.json']:
            path=f'jssa/theory/posdim-identities/{folder}/{cid}/{name}'
            raw=subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT)
            assert len(raw)<16*1024**2
            (dest/name).write_bytes(raw)
            manifest.append(dict(source=ref+':'+path,sha256=hashlib.sha256(raw).hexdigest()))
    save(OUT/'legacy-provenance.json',manifest)

def legacy_verify():
    checks=[]
    for d in sorted((OUT/'legacy').iterdir()):
        lines=(d/'system.txt').read_text().splitlines();meta=json.loads((d/'result.json').read_text())
        fs=[sp.sympify(l.split('=',1)[1]) for l in lines if l.startswith('F') and '=' in l]
        s=sp.sympify(next(l.split('=',1)[1] for l in lines if l.startswith('nondegeneracy s')))
        cofs=[sp.sympify(l.split('=',1)[1]) for l in (d/'certificate.txt').read_text().splitlines() if l.startswith('C') and '=' in l]
        # Last equation is Rabinowitsch when s is nonconstant; historical cofactors clear it.
        if len(fs)==len(cofs)+1:fs=fs[:-1]
        assert len(fs)==len(cofs)
        q=sp.sympify(meta['P'] if meta['member'] else meta['elim_poly'])
        vs=sorted(set().union(s.free_symbols,q.free_symbols,*[f.free_symbols for f in fs],*[c.free_symbols for c in cofs]),key=str)
        cert=dict(variables=list(map(str,vs)),N=meta['N'],s=sparse(s,vs),Q=sparse(q,vs),F=[sparse(f,vs) for f in fs],C=[sparse(c,vs) for c in cofs])
        with deadline(60):ok=verify(cert)
        assert ok,d.name
        checks.append(dict(id=d.name,exact_fraction_check=ok,terms=sum(len(c) for c in cert['C'])))
    save(OUT/'legacy-verification.json',checks)

def charts():
    rows=[]
    # H's four certificates are reused as evidence and rechecked independently.
    for cid in ['AIME-2011-II-04','aime-2003-1-12','JMO-2013-PRE-05','HMMT-2023-FEB-GEO-01']:
        path=HERE.parent/'H/certificates'/f'{cid}.json';d=json.loads(path.read_text())
        rows.append(identity(cid,sp.symbols(' '.join(d['variables'])),list(map(sp.sympify,d['F'])),sp.sympify(d['P']),
            list(map(sp.sympify,d['C'])),sp.sympify(d['s']),d['N'],d['nonzero_reason'],
            'H/certificates/'+cid+'.json; SHA256='+hashlib.sha256(path.read_bytes()).hexdigest()))
    d,l=sp.symbols('d l')
    rows.append(identity('AIME-2015-II-07',[d,l,T],[5*d-36,l-25,l*T-d],125*T-36,reason='fixed triangle; moving rectangle absent from target'))
    d,e,g,w=sp.symbols('d e g w')
    rows.append(identity('AIME-2016-I-06',[d,e,g,w,T],[d-3,e-2,g-d-e,w-g*g+d*d,w-d*(T+e)],3*T-10,
                         reason='C,I,L,D order; arc midpoint lemma gives DA=DB=DI=g'))
    h,r=sp.symbols('h r')
    rows.append(identity('AIME-2021-I-13',[h,r,T],[T*h-336*r,4*h*h-r*r],T*T-672**2,
                         [4*(T*h+336*r),-T*T],r,2,'r>0 from original DSL; target d>0'))
    u,w=sp.symbols('u w')
    rows.append(identity('HMMT-2006-FEB-GEO-03',[u,w,T],[w+30,27*u+w+813,T*T-u*u+4*w],T*T-961,
                         [-4-(u-29)/27,(u-29)/27,1],reason='secant powers at P,Q; target is nonnegative chord length'))
    k=sp.Symbol('k')
    rows.append(identity('HMMT-2008-FEB-GEO-06',[k,T],[k*k-16,T*T-k*k-1],T*T-17,[1,1],reason='circumcenter=(1,k), inscribed angle pi/4'))
    x,y,h=sp.symbols('x y h')
    rows.append(identity('HMMT-2013-FEB-GEO-02',[x,y,h,T],[x*x+y*y-11*x-2*h*y+24,sp.Rational(11,2)*x+h*y-x*x-y*y,T*T-x*x-y*y],T*T-24,[-1,-2,1],reason='equal lengths and perpendicularity; Distance(A,E)>0'))
    X,Y,Z,U=sp.symbols('X Y Z U');s=(X+3)*(Y+2)*(Z+1)
    fs=[X*X-9,Y*Y-4,Z*Z-1,U-X-Y-Z,T-U*U+14]
    cofs=[(U+6)*(Y+2)*(Z+1),(U+6)*(X+3)*(Z+1),(U+6)*(X+3)*(Y+2),s*(U+6),s]
    rows.append(identity('HMMT-2013-FEB-GEO-03',[X,Y,Z,U,T],fs,T-22,cofs,s,1,
                         'OnSegment makes X,Y,Z nonnegative; positive corner areas make all positive; U=sqrt(p*v/2)>0'))
    # Relaxed signed-area chart: all sign combinations, before real-branch exclusions.
    signrows=[]
    for a,b,c in itertools.product([-1,1],repeat=3):
        uu=3*a+2*b+c;signrows.append(dict(X=3*a,Y=2*b,Z=c,U=uu,T=uu*uu-14,allowed=(a==b==c==1)))
    save(OUT/'hexagon-sign-branches.json',signrows)
    k,c,sn=sp.symbols('k c sn')
    rows.append(identity('HMMT-2013-FEB-GEO-08',[k,c,sn,T],[13*k+42,c*c+sn*sn-1,T*T-k*k*(c*c+sn*sn)],169*T*T-1764,
                         [13*k-42,169*k*k,169],reason='C=(21c/5,0), Q=(k*c,-k*sn); c=cos(g),sn=sin(g)'))
    k,w=sp.symbols('k w')
    rows.append(identity('HMMT-2022-FEB-GEO-01',[k,w,T],[k*k-3,2*w-9-11*k*k,T*T-w*w],T*T-441,
                         [11*(w+21)/2,(w+21)/2,1],reason='unit direction of UV=(-1/2,sqrt(3)/2); w is projection of BC'))
    a,b,f=sp.symbols('a b f')
    rows.append(identity('aime-2000-2-6',[a,b,f,T],[a-b-100,3*a-7*b,T-(1-f)*a-f*b,2*f*(a+T)-a-b],T*T-18125,
                         reason='height>0, top_right>top_left, base>0, 0<f<1 fix all length/area signs'))
    p,q,r=sp.symbols('p q r');S=p+q+r
    fs=[S-sp.Rational(2,3),p*p+q*q+r*r-sp.Rational(2,5),T-1+S-p*q-q*r-r*p]
    rows.append(identity('aime-2001-1-9',[p,q,r,T],fs,45*T-16,[45*(S/2-sp.Rational(2,3)),-sp.Rational(45,2),45],
                         reason='p,q,r in (0,1) give the oriented inner-triangle area ratio'))
    assert len(rows)==15
    save(OUT/'chart-summary.json',rows)

def jmo_counterexample():
    a,t=sp.symbols('a t',real=True)
    X=sp.Matrix([(5*a-15)/2,(15-3*a)/2]);Y=sp.Matrix([5*a-20,4*a-20])
    Z=sp.Matrix([t*(a-4)/(4-t),4*(t-a)/(4-t)])
    cross=lambda u,v:sp.det(sp.Matrix.hstack(u,v))
    det=sp.factor(cross(Y-X,Z-X));expected=(a-5)*(a-4)*(60-23*t)/(4-t)
    assert sp.cancel(det-expected)==0
    result=dict(id='JMO-2014-PRE-09',coordinate_change='rotate -pi/4; a=s/sqrt(2)',
                determinant=str(det),domain='a>=5, 0<t<=a, t!=4; raw OnSegment includes endpoints',
                boundary_family='a=5; every t in (0,5] except 4 is an exact DSL solution',
                nonboundary='a>5 forces t=60/23',witnesses=[])
    from geosolver import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from mpmath import mp
    dsl=json.loads((HERE/'inputs/JMO-2014-PRE-09.json').read_text())['dsl']
    bundle=load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document());ev=build_ir_evaluator(bundle)
    O=sp.Matrix([0,0]);A=sp.Matrix([0,5]);B=sp.Matrix([5,0]);C=sp.Matrix([0,-5]);D=sp.Matrix([-5,0])
    P=sp.Matrix([0,3]);Q=sp.Matrix([5,0]);R=sp.Matrix([0,-4])
    norm=lambda v:sp.sqrt(sp.expand(v.dot(v)))
    for tt in [1,2]:
        S=sp.Matrix([-tt,0]);xx=X.subs(a,5);yy=Y.subs(a,5);zz=Z.subs({a:5,t:tt})
        residuals=[norm(P-O)-3,norm(Q-O)-5,norm(R-O)-4,cross(yy-xx,zz-xx)]
        residuals += [norm(V-O)+norm(V-W)-norm(W-O) for V,W in [(P,A),(Q,B),(R,C),(S,D)]]
        residuals += [cross(xx-A,B-A),cross(xx-P,Q-P),cross(yy-B,C-B),cross(yy-Q,R-Q),cross(zz-C,D-C),cross(zz-R,S-R)]
        residuals=list(map(sp.simplify,residuals));assert all(v==0 for v in residuals)
        w=dict(s='5*sqrt(2)',t=tt,target=tt,exact_residuals=list(map(str,residuals)),
               rotated_X=list(map(str,xx)),rotated_Y=list(map(str,yy)),rotated_Z=list(map(str,zz)),
               all_exact_constraints=True,intersection_determinants=[str(cross(B-A,Q-P)),str(cross(C-B,R-Q)),str(cross(D-C,S-R))])
        assert all(sp.sympify(v)!=0 for v in w['intersection_determinants'])
        with mp.workdps(100),high_precision_mode():
            values={'s':5*mp.sqrt(2),'t':mp.mpf(tt)};v=[values[n] for n in bundle.var_names]
            rr=ev.evaluate_hp_residual(v,precision=100).residual_vector
            hard=ev.evaluate_hp_hard_feasibility(v,precision=100,include_margins=True)
            ans=ev.evaluate_answer_hp(v,precision=100).answer_hp
            w.update(hp_residual_max=mp.nstr(max(map(abs,rr)),12),hp_hard_feasible=bool(hard.hard_feasible),hp_target=mp.nstr(ans,100),variable_order=list(bundle.var_names))
        result['witnesses'].append(w)
    save(OUT/'JMO-2014-PRE-09-counterexample.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)

def root_tables():
    roots=[]
    # Old non-P certificates on the genuine cohort, including all 16 roots of the saturated trapezoid.
    old={
      'HMMT-2006-FEB-GEO-03':(T*T-961,T-31,'T>=0'),
      'HMMT-2013-FEB-GEO-08':(169*T*T-1764,13*T-42,'T>0'),
      'HMMT-2022-FEB-GEO-01':(T*T-441,T-21,'T>=0'),
      'aime-2001-1-9':(2025*T*T-256,45*T-16,'T>=0'),
      'aime-2000-2-6':(sp.prod(T*T-v for v in [352500,252500,43125,18125,6900,3525,2900,2525]),T*T-18125,'T>0; real area and order imply a=175,b=75,T^2=18125'),
      'HMMT-2023-FEB-GEO-01':((T*T-189**2)*(T*T-51**2),T-189,'T>=0; 0<py<sqrt(3)*s/2 fixes signed areas'),
      'AIME-2021-I-13':(T*T-672**2,T-672,'d>0,r>0'),
    }
    for cid,(E,P,reason) in old.items():
        items=[]
        for v in sp.Poly(E,T).real_roots():
            retained=sp.simplify(P.subs(T,v))==0 and v>0
            items.append(dict(root=str(v),positive=bool(v>0),retained=bool(retained),
                              exclusion='retained' if retained else 'nonpositive length/area' if v<0 else reason))
        roots.append(dict(id=cid,E=str(sp.factor(E)),P=str(P),roots=items,unique_retained=sum(i['retained'] for i in items)==1))
    save(OUT/'root-exclusions.json',roots)

if __name__=='__main__':
    copy_history();charts();jmo_counterexample();root_tables();legacy_verify()
    print('15 real-chart identities, complete listed-root exclusions, and JMO boundary audit verified.')
