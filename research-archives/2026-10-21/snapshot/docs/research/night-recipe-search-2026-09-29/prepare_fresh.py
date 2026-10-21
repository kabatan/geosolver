"""Six exact, frozen confirmation questions from original constructions.

No target relation is used to construct any answer. Sympy's rational/radical
geometry is checked against a separate 60-digit complex implementation.
"""
import json,runpy,sys
from pathlib import Path
import sympy as s
import mpmath as mp
from prepare_data import RUN,ROOT,write,sha
import independent_geometry as g
V=lambda x,y:s.Matrix([s.sympify(x),s.sympify(y)])
def simp(x):return s.simplify(x)
def cross(a,b):return s.det(s.Matrix.hstack(a,b))
def d2(a,b):return s.factor((a-b).dot(a-b))
def length(a,b):return simp(s.sqrt(d2(a,b)))
def line(a,b,c,d):return simp(a+cross(c-a,d-c)/cross(b-a,d-c)*(b-a))
def foot(p,a,b):return simp(a+(p-a).dot(b-a)/d2(a,b)*(b-a))
def center(a,b,c):return simp(s.Matrix.vstack((2*(b-a)).T,(2*(c-a)).T).inv()*s.Matrix([b.dot(b)-a.dot(a),c.dot(c)-a.dot(a)]))
def second(o,a,v):return simp(a-2*(a-o).dot(v)/v.dot(v)*v)
def eq(a,b=0):assert simp(a-b)==0,(a,b)
def pos(x):assert float(s.N(x))>1e-10,x
def acute(a,b,c):
    for p,q,r in [(a,b,c),(b,c,a),(c,a,b)]:pos((q-p).dot(r-p))
    assert len({d2(a,b),d2(a,c),d2(b,c)})==3
def encode(x):
    if isinstance(x,s.MatrixBase):return [str(simp(v)) for v in x]
    if isinstance(x,dict):return {k:encode(v) for k,v in x.items()}
    return str(simp(x))
def angle_eq(a,b,c,d):
    eq(a.dot(b)**2*c.dot(c)*d.dot(d),c.dot(d)**2*a.dot(a)*b.dot(b))
    assert float(a.dot(b))*float(c.dot(d))>=0
def make_h02(w,ax,ay,i1,i2):
    a,b,c=V(ax,ay),V(-w,0),V(w,0);acute(a,b,c);m=(b+c)/2;k=foot(a,b,c)
    pos(d2(b,k)-d2(k,c));p={'A':a,'B':b,'C':c,'M':m,'K':k};zs=[]
    for index,ii in enumerate([i1,i2],1):
        d=b+V(ii,0);pos(ii);pos(2*w-ii)
        u=second(center(a,b,d),a,c-a);v=second(center(a,c,d),a,b-a);z=center(a,u,v)
        p.update({f'D{index}':d,f'U{index}':u,f'V{index}':v,f'Z{index}':z});zs.append(z)
    return p,dict(BC=length(b,c),AM=length(a,m),AK=length(a,k),BD1=s.Integer(i1),BD2=s.Integer(i2)),length(*zs)
def make_da15(bx,cx,h):
    a,b,c=V(0,h),V(bx,0),V(cx,0);acute(a,b,c);m=(b+c)/2
    def pb(p,q):
        v=q-p;mid=(p+q)/2
        return line(mid,mid+V(-v[1],v[0]),a,m)
    d,e=pb(a,b),pb(a,c);f=line(b,d,c,e);o=center(a,b,c)
    for q in [d,e]:pos((q-a).dot(m-a))
    for p,q,r in [(a,b,c),(b,c,a),(c,a,b)]:pos(cross(q-p,f-p)*cross(q-p,r-p))
    return dict(A=a,B=b,C=c,M=m,D=d,E=e,F=f,O=o),dict(AO=length(a,o),AF=length(a,f)),length(o,f)
def make_db08(cx,h):
    a,b,c=V(0,h),V(-1,0),V(cx,0);acute(a,b,c);pos(d2(a,c)-d2(a,b));o=center(a,b,c)
    v=a-o;p=line(a,a+V(-v[1],v[0]),b,c);x=foot(a,o,p)
    def angular(base,v,w,end):
        good=[];co,det=v.dot(w),cross(v,w)
        for sign in [1,-1]:
            dr=V(co*base[0]+sign*det*base[1],-sign*det*base[0]+co*base[1]);q=line(x,x+dr,a,end)
            if float((q-x).dot(dr))>0 and float(cross(p-o,q-o)*cross(p-o,a-o))>0:good.append(q)
        assert len(good)==1
        return good[0]
    e=angular(p-x,a-c,x-c,b);f=angular(o-x,a-b,x-b,c)
    angle_eq(e-x,p-x,a-c,x-c);angle_eq(f-x,o-x,a-b,x-b)
    # Explicit intersections with Gamma, then the circumcenter of K,L,X.
    t=s.symbols('t');z=e+t*(f-e);roots=s.solve(d2(z,o)-d2(a,o),t);assert len(roots)==2
    k,l=[simp(z.subs(t,r)) for r in roots];u=center(k,l,x);radius=length(u,x)
    unit=simp((p-u)/length(p,u));y=simp(u+radius*unit);zz=simp(u-radius*unit)
    for q in [k,l,x]:eq(d2(u,q),radius**2)
    pos(d2(p,u)-radius**2);pos((y-p).dot(u-p));pos((u-y).dot(u-p));pos((zz-u).dot(u-p))
    return dict(A=a,B=b,C=c,O=o,P=p,X=x,E=e,F=f,K=k,L=l,U=u,Y=y,Z=zz),dict(PY=length(p,y),YZ=length(y,zz)),length(p,x)
def independent(cid,pts):
    p={k:mp.mpc(str(s.N(v[0],60)),str(s.N(v[1],60))) for k,v in pts.items()};a,b,c=p['A'],p['B'],p['C']
    if cid=='H02':
        zs=[]
        for i in [1,2]:
            d=p[f'D{i}'];u=g.other(g.lc(a,c,g.circle(a,b,d)),a);v=g.other(g.lc(a,b,g.circle(a,c,d)),a);zs.append(g.circle(a,u,v)[0])
        return abs(zs[0]-zs[1])
    if cid=='DA15':
        m=(b+c)/2
        d=g.line((a+b)/2,(a+b)/2+g.j*(b-a),a,m);e=g.line((a+c)/2,(a+c)/2+g.j*(c-a),a,m)
        return abs(g.line(b,d,c,e)-g.circle(a,b,c)[0])
    o,r=g.circle(a,b,c);pp=g.line(a,a+g.j*(a-o),b,c);x=g.foot(a,o,pp)
    # The requested PX depends only on these original constructions.
    assert abs(x-p['X'])<mp.mpf('1e-45') and abs(pp-p['P'])<mp.mpf('1e-45')
    return abs(pp-x)
def main():
    templates=runpy.run_path(str(ROOT/'docs/research/qwen35-diverse-sft-2026-09-24/english_templates.py'))['NUMERIC_EN']
    cases=[('H02',make_h02(7,3,9,4,9)),('H02',make_h02(8,4,10,5,10)),('DA15',make_da15(-2,4,4)),('DA15',make_da15(-3,5,5)),('DB08',make_db08(3,4)),('DB08',make_db08(2,3))]
    jobs=[];keys=[];witness=[];seen=set()
    for i,(cid,(points,givens,answer)) in enumerate(cases):
        lengths=sorted([float(d2(points['A'],points['B'])),float(d2(points['A'],points['C'])),float(d2(points['B'],points['C']))]);sig=tuple(round(v/lengths[-1],12) for v in lengths)
        assert (cid,sig) not in seen;seen.add((cid,sig))
        verified=independent(cid,points);error=abs(verified-mp.mpf(str(s.N(answer,55))));assert error<mp.mpf('1e-40')
        ident=f'fresh-{cid.lower()}-{i%2+1}'
        prompt='Solve the following geometry problem. Give the exact numerical answer and explain your reasoning in English. You have no access to tools.\n\n'+templates[cid].format(**encode(givens))+'\n\nEnd with a single line of the form Answer: <exact numerical expression>.'
        jobs.append(dict(id=ident,source_id=cid,variant='new-nonsimilar',seed=2026093401+i,messages=[dict(role='user',content=prompt)]))
        keys.append(dict(id=ident,source_id=cid,answer_exact=str(answer)))
        witness.append(dict(id=ident,source_id=cid,points=encode(points),givens=encode(givens),answer=str(answer),shape_signature=sig,independent_answer_60digit=mp.nstr(verified,55),independent_absolute_error=str(error)))
    write('jobs/fresh6.json',jobs);write('keys/fresh6.json',keys);write('fresh6-witnesses.researcher-only.json',witness)
    write('jobs/confirmation18.json',json.loads((RUN/'jobs/confirm-old.json').read_text())+jobs)
    write('keys/confirmation18.json',json.loads((RUN/'keys/confirm-old.json').read_text())+keys)
    write('fresh6-receipt.json',dict(status='pass',construction='exact rational/radical original-geometry intersections; target identities not used',independent_check='60-digit elementary geometry',driver_sha256=sha(__file__),cases=6))
    print(json.dumps(keys))
if __name__=='__main__':main()
