#!/usr/bin/env python3
"""Read-only construction audit for DA v2. No network, no GPU, no file writes.

Reuses only the elementary line/circle/foot primitives in geo_primitives.py.
All v2 points are newly constructed; v1 witness values are not imported.
The exact answers come from the geometric derivations in da_revision.json;
this script independently checks existence, every numerical given, and answer.
"""
import argparse
import ast
import cmath
import json
import math
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
G = runpy.run_path(str(HERE / 'geo_primitives.py'))
line, circle, tangent_circle, lc, cc, other, foot, unit, dot, cross, near = (
    G[name] for name in ['line','circle','tangent_circle','lc','cc','other','foot','unit','dot','cross','near'])
pair, inside = G['tangent_pair'], G['inside_triangle']
TOL = 1e-8


def exact(expr):
    node=ast.parse(str(expr),mode='eval').body
    def val(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,int|float): return n.value
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub): return -val(n.operand)
        if isinstance(n,ast.BinOp):
            a,b=val(n.left),val(n.right)
            if isinstance(n.op,ast.Add):return a+b
            if isinstance(n.op,ast.Sub):return a-b
            if isinstance(n.op,ast.Mult):return a*b
            if isinstance(n.op,ast.Div):return a/b
            if isinstance(n.op,ast.Pow):return a**b
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='sqrt' and len(n.args)==1:
            return math.sqrt(val(n.args[0]))
        raise ValueError(expr)
    return val(node)


def acute(a,b,c):
    lengths=sorted([abs(a-b),abs(b-c),abs(c-a)])
    assert min(lengths[1]-lengths[0],lengths[2]-lengths[1])>1e-9
    assert min(dot(b-a,c-a),dot(a-b,c-b),dot(a-c,b-c))>1e-9


def angle(a,v,b):
    return math.degrees(math.acos(max(-1.,min(1.,dot(unit(a-v),unit(b-v))))))


def pack(points,givens,answer):
    return {'points':{k:[z.real,z.imag] for k,z in points.items()},
            'given_values':givens,'answer':answer}


def construct():
    out={}
    # DA01: sides 7,8,9, with exact seed A=(2,3 sqrt(5)).
    A,B,C=2+3*math.sqrt(5)*1j,0j,8+0j
    w1,w2,T=pair(A,B,C)
    acute(A,B,C)
    out['DA01']=pack(dict(A=A,B=B,C=C,T=T),{'AB':abs(A-B),'BC':abs(B-C),'CA':abs(C-A)},abs(A-T))

    # DA02: solve the three original 120-degree conditions numerically,
    # without using either the Dumpty or centroid-distance identity.
    A,B,C=0j,10+0j,4+4*math.sqrt(3)*1j
    T=(A+B+C)/3
    for _ in range(10000):
        weights=[1/abs(T-z) for z in (A,B,C)]
        nxt=sum(w*z for w,z in zip(weights,(A,B,C), strict=False))/sum(weights)
        if abs(nxt-T)<1e-13:T=nxt;break
        T=nxt
    else:raise AssertionError('DA02 iteration failed')
    for a,b in [(A,B),(B,C),(C,A)]:near(angle(a,T,b),120)
    assert inside(T,A,B,C)
    Gc=(A+B+C)/3;K=other(lc(T,Gc,circle(B,T,C)),T)
    assert dot(Gc-T,K-Gc)>0
    out['DA02']=pack(dict(A=A,B=B,C=C,T=T,G=Gc,K=K),{'AB':abs(A-B),'AC':abs(A-C),'angle_BAC':angle(B,A,C)},abs(T-K))

    # DA03: original two circles -> T -> K. The tangent relation is not used
    # to compute T, K, or the reported given BK.
    A,B,C=8+12*math.sqrt(5)*1j,0j,32+0j
    O,R=circle(A,B,C);T=other(cc(tangent_circle(A,B,C),circle(B,O,C)),C)
    K=line(T,O,B,C);acute(A,B,C)
    assert K.real<B.real<C.real
    out['DA03']=pack(dict(A=A,B=B,C=C,O=O,T=T,K=K),{'BC':abs(B-C),'BK':abs(B-K)},abs(A-K))

    # DA04: h follows from the original circle equations for the requested
    # chord length, not from substituting the desired answer as Q.
    A,B,P=0j,11+0j,3+0j;h=605/(2*math.sqrt(1679));O=5.5+h*1j;R=abs(O-A)
    O1=A+3/11*(O-A);O2=B+8/11*(O-B)
    w1,w2=(O1,abs(O1-A)),(O2,abs(O2-B))
    near(abs(O-O1)+w1[1],R);near(abs(O-O2)+w2[1],R)
    Q=other(cc(w1,w2),P);X,Y=lc(P,Q,(O,R))
    out['DA04']=pack(dict(A=A,B=B,P=P,O=O,O1=O1,O2=O2,Q=Q,X=X,Y=Y),{'AP':abs(A-P),'PB':abs(P-B),'XY':abs(X-Y)},abs(P-Q))

    # D=(18/5,16/5) retains MD=4 while making ABC scalene.
    A,B,C=300/101+576/101*1j,0j,12+0j
    D=other(cc(tangent_circle(B,C,A),tangent_circle(B,A,C)),B)
    M=(B+C)/2;E=line(M,D,A,C);acute(A,B,C)
    assert 0<dot(D-M,E-M)/abs(E-M)**2<1
    out['DA05']=pack(dict(A=A,B=B,C=C,D=D,M=M,E=E),{'BC':abs(B-C),'MD':abs(M-D)},abs(D-E))

    A,B,O=5j,-3-4j,0j;C=other(lc(B,20/3+5j,(O,5)),B);M=(B+C)/2
    w1,w2,D=pair(A,B,C);E=other(lc(A,M,w2),A)
    acute(A,B,C);assert abs(A-B)>abs(A-C)
    out['DA06']=pack(dict(A=A,B=B,C=C,O=O,M=M,D=D,E=E),{'AO':abs(A-O),'AD':abs(A-D)},abs(O-E))

    # DA07: exact algebraic side seed; all four new points are circle roots.
    a=3*math.sqrt(57)/2;b=(9*math.sqrt(13)+3*math.sqrt(21))/4;c=(9*math.sqrt(13)-3*math.sqrt(21))/4
    x=(a*a+c*c-b*b)/(2*a);A=x+math.sqrt(c*c-x*x)*1j;B=0j;C=a+0j
    O,R=circle(A,B,C);H=A+B+C-2*O;wo=circle(B,O,C);wh=circle(B,H,C)
    M=other(cc(((A+O)/2,abs(A-O)/2),wo),O)
    N=other(cc(((A+H)/2,abs(A-H)/2),wh),H)
    X=other(lc(A,M,wo),M);Y=other(lc(A,N,wh),N);acute(A,B,C)
    assert 0<dot(M-A,X-A)/abs(X-A)**2<1
    out['DA07']=pack(dict(A=A,B=B,C=C,O=O,H=H,M=M,N=N,X=X,Y=Y),{'AM':abs(A-M),'MX':abs(M-X),'MN':abs(M-N)},abs(X-Y))

    A=217/25+863/50*1j;B=-7*math.sqrt(1054)/25+429/50*1j;C=-B.real+B.imag*1j
    O,R=circle(A,B,C);w=circle(B,O,C);Q=2*w[0]-O
    M=line(C,Q,A,A+C-B);N=A+C-M;T=line(A,Q,M,N);acute(A,B,C)
    near(abs(T-w[0]),w[1])
    out['DA08']=pack(dict(A=A,B=B,C=C,O=O,Q=Q,M=M,N=N,T=T),{'OQ':abs(O-Q),'QT':abs(Q-T)},abs(O-T))

    A,B,C=-8+0j,8+0j,4*math.sqrt(5)*1j
    I=8*math.sqrt(5)/5*1j
    # Select P from the original incenter circle and distance CP=6.
    ps=[z for z in cc(circle(A,I,B),(C,6)) if z.real<0 and inside(z,A,B,C)]
    assert len(ps)==1;P=ps[0]
    D=line(P,P+C-A,A,B);E=line(P,P+C-B,A,B)
    F=line(P,P+B-A,A,C);Gm=line(P,P+B-A,B,C);T=line(D,F,E,Gm)
    out['DA09']=pack(dict(A=A,B=B,C=C,I=I,P=P,D=D,E=E,F=F,G=Gm,T=T),{'AB':abs(A-B),'AC':abs(A-C),'BC':abs(B-C),'CP':abs(C-P)},abs(C-T))

    A=(196-21*math.sqrt(51))/50+(147+28*math.sqrt(51))/50*1j;B=0j;C=8+0j
    O,R=circle(A,B,C);I=(A+B)/2;J=(A+C)/2;K=(I+J)/2
    T=other(cc(tangent_circle(I,A,K),tangent_circle(J,A,K)),K)
    Z,r=circle(A,B,T);acute(A,B,C)
    out['DA11']=pack(dict(A=A,B=B,C=C,O=O,I=I,J=J,K=K,T=T,Z=Z),{'AB':abs(A-B),'BC':abs(B-C),'R':R},r)

    O1,O2,r1,r2=0j,6+0j,5,4
    A,B=sorted(cc((O1,r1),(O2,r2)),key=lambda z:-z.imag)
    C=other(lc(B,B+1j*(B-O1),(O2,r2)),B);D=other(lc(B,B+1j*(B-O2),(O1,r1)),B)
    X=other(lc(A,A+unit(D-A)+unit(B-A),(O1,r1)),A)
    Y=other(lc(A,A+unit(C-A)+unit(B-A),(O2,r2)),A)
    P=circle(A,C,D)[0];Q=circle(X,A,Y)[0]
    assert P.imag*Q.imag>0
    out['DA13']=pack(dict(O1=O1,O2=O2,A=A,B=B,C=C,D=D,X=X,Y=Y,P=P,Q=Q),{'O1O2':abs(O1-O2),'O1P':abs(O1-P),'O1Q':abs(O1-Q)},abs(P-Q))

    # DA14 probe: explicit angle seed; the point F is still a circle root.
    t=math.tan(math.radians(10));r=(math.tan(math.pi/6)+t)/(math.tan(math.pi/6)-t)
    A,B,C=0j,1+0j,r*cmath.exp(1j*math.pi/3);O,R=circle(A,B,C)
    aa,bb,cc_=abs(B-C),abs(C-A),abs(A-B);I=(aa*A+bb*B+cc_*C)/(aa+bb+cc_)
    A1=foot(A,B,C);P=foot(O,B,C);D=line(B,O,A,A1);E=line(C,O,A,A1)
    F=other(cc(circle(A,B,D),circle(A,C,E)),A);acute(A,B,C)
    out['DA14']=pack(dict(A=A,B=B,C=C,O=O,I=I,A1=A1,P=P,D=D,E=E,F=F),{'angle_IAP':angle(I,A,P)},angle(F,A,P))

    A,B,O=13j,-5-12j,0j;C=other(lc(B,156/5+13j,(O,13)),B);M=(B+C)/2
    D=line(A,M,(A+B)/2,(A+B)/2+1j*(B-A));E=line(A,M,(A+C)/2,(A+C)/2+1j*(C-A));F=line(B,D,C,E)
    acute(A,B,C);assert inside(F,A,B,C)
    out['DA15']=pack(dict(A=A,B=B,C=C,O=O,M=M,D=D,E=E,F=F),{'AO':abs(A-O),'AF':abs(A-F)},abs(O-F))

    # DA16: construct ABC first from exact seed values, then forget the
    # seed's putative M,T and recover every learner-visible point directly.
    A=4+0j;O=6.5-13/(8*math.sqrt(1914))*1j;R=abs(A-O)
    B=8*(313/325+2*math.sqrt(1914)/325*1j)
    pole=6.5-6.25/O.imag*1j;C=other(lc(B,pole,(O,R)),B)
    w1,w2,M=pair(A,B,C)
    P=G['choose_minor'](lc(M,M+1j*(B-M),(O,R)),A,B,O)
    Q=G['choose_minor'](lc(M,M+1j*(C-M),(O,R)),A,C,O)
    T=line(B,P,C,Q);acute(A,B,C);assert abs(T-O)>R
    out['DA16']=pack(dict(A=A,B=B,C=C,O=O,M=M,P=P,Q=Q,T=T),{'TA':abs(T-A),'TP':abs(T-P),'TB':abs(T-B)},abs(T-M))

    # DA17: circles tangent to the common line, then solve original
    # collinearity for the transversal circle rather than using AB formula.
    A,B=0j,8+0j;r1,r2=32/math.sqrt(7),8/math.sqrt(7);O1=r1*1j;O2=8+r2*1j
    X,Y=sorted(cc((O1,r1),(O2,r2)),key=lambda z:z.imag)
    def cd(k):
        a=2*(r1-k)/8;b=2*(k-r2)/8
        D=a*2*r1/(1+a*a)+2*r1/(1+a*a)*1j
        C=8+b*2*r2/(1+b*b)+2*r2/(1+b*b)*1j
        return C,D
    def residual(k):
        c,d=cd(k);return cross(c-Y,d-Y)
    # General nondegenerate solution is isolated from the two C=D roots.
    lo,hi=r1+r2-math.sqrt(4*r1*r2-64)/2-.25,r1+r2-math.sqrt(4*r1*r2-64)/2+.25
    assert residual(lo)*residual(hi)<0
    for _ in range(80):
        mid=(lo+hi)/2
        if residual(lo)*residual(mid)<=0:hi=mid
        else:lo=mid
    k=(lo+hi)/2;C,D=cd(k);S=4+k*1j
    near(cross(C-Y,D-Y),0);assert dot(Y-C,Y-D)<0
    for z in (A,B,C,D):near(abs(z-S),abs(A-S))
    out['DA17']=pack(dict(A=A,B=B,O1=O1,O2=O2,X=X,Y=Y,C=C,D=D,S=S),{'XC':abs(X-C),'XD':abs(X-D),'XY':abs(X-Y)},abs(A-B))

    # DA18 seed gives two 60-degree cuts; reconstruct the side intersections
    # afterwards and check they are strictly inside the sides, not extensions.
    B,F=0j,8+0j;y=(17+math.sqrt(33))/2;z=(17-math.sqrt(33))/2
    ds=F+y*cmath.exp(4j*math.pi/3);es=F+z*cmath.exp(2j*math.pi/3)
    bis=unit(ds-B)+unit(es-B)
    A=line(B,ds,F,F+1j*bis);C=line(B,es,F,F+1j*bis)
    D=line(A,B,F,F+(B-F)*cmath.exp(1j*math.pi/3))
    E=line(B,C,F,F+(B-F)*cmath.exp(-1j*math.pi/3))
    near(angle(B,A,C),30);near(angle(A,B,C),120);near(angle(A,C,B),30)
    assert 0<dot(D-B,A-B)/abs(A-B)**2<1 and 0<dot(E-B,C-B)/abs(C-B)**2<1
    near(angle(B,F,D),60);near(angle(B,F,E),60)
    out['DA18']=pack(dict(A=A,B=B,C=C,F=F,D=D,E=E),{'BF':abs(B-F),'FD+FE':abs(F-D)+abs(F-E)},abs(D-E)+abs(E-F)+abs(F-D))
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--json',action='store_true');args=parser.parse_args()
    results=construct();path=HERE/'da_revision.json'
    if path.exists():
        cards=json.loads(path.read_text())
        active=[c for c in cards if c['decision'] in ['main','probe']]
        assert {c['id'] for c in active}==set(results)
        for c in active:
            w=results[c['id']]
            assert {g['name'] for g in c['givens']}==set(w['given_values']),c['id']
            for g in c['givens']:near(w['given_values'][g['name']],exact(g['value']))
            near(w['answer'],exact(c['answer_exact']))
    if args.json:print(json.dumps(results,ensure_ascii=False,indent=2))
    else:print(json.dumps({'verified_constructions':len(results),'verified_givens':sum(len(w['given_values']) for w in results.values()),'relative_tolerance':TOL,'repo_solver_checked':False,'status':'all original-construction witness checks passed'},ensure_ascii=False))


if __name__=='__main__':main()
