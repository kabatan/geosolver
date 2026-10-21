#!/usr/bin/env python3
"""CPU-only exact witnesses for DB v2. No hidden relation generates an answer.

Default prints a compact pass report; --json emits research-only witnesses.
Every witness starts with triangle/circle input coordinates, reproduces the
problem's intersections, and checks the short solution only afterwards.
"""
import argparse
import json
from pathlib import Path

import sympy as s

V=lambda x,y:s.Matrix([s.sympify(x),s.sympify(y)])
R=s.Rational

def simp(x):return s.simplify(x)
def d2(x,y):return s.factor((x-y).dot(x-y))
def cross(x,y):return s.det(s.Matrix.hstack(x,y))
def eq(x,y=0):
    z=simp(x-y)
    assert z==0,str(z)[:500]
def pos(x):assert float(s.N(x))>0

def center(a,b,c):
    mat=s.Matrix.vstack((2*(b-a)).T,(2*(c-a)).T)
    return simp(mat.inv()*s.Matrix([b.dot(b)-a.dot(a),c.dot(c)-a.dot(a)]))
def line(a,b,c,d):return simp(a+cross(c-a,d-c)/cross(b-a,d-c)*(b-a))
def foot(p,a,b):return simp(a+(p-a).dot(b-a)/d2(a,b)*(b-a))
def other(o,a,v):return simp(a-2*(a-o).dot(v)/v.dot(v)*v)
def common(o1,o2,a):
    v=o2-o1
    return other(o1,a,V(-v[1],v[0]))
def angle_eq(a,v,b,c,w,d):
    u1,u2,v1,v2=a-v,b-v,c-w,d-w;p,q=u1.dot(u2),v1.dot(v2)
    eq(p*p*v1.dot(v1)*v2.dot(v2),q*q*u1.dot(u1)*u2.dot(u2))
    assert float(s.N(p))*float(s.N(q))>=0

def fmt(x):
    if isinstance(x,s.MatrixBase):return [s.sstr(simp(y)) for y in x]
    if isinstance(x,dict):return {k:fmt(v) for k,v in x.items()}
    if isinstance(x,list|tuple):return [fmt(y) for y in x]
    return s.sstr(simp(x))
def rec(points,givens,answer):return {'points':fmt(points),'given_values':fmt(givens),'answer':fmt(answer)}
def positive_sqrt(x):return simp(s.sqrtdenest(s.sqrt(s.factor(x))))

def build_db06():
    # DB06: solve each angle condition on its prescribed diagonal.
    A,B,C,D=V(0,0),V(11*s.sqrt(3)/12,-s.sqrt(213)/12),V(2*s.sqrt(3),0),V(5*s.sqrt(3)/6,s.sqrt(213)/6)
    def angle_point(a,b,v,w,ra,rv,rb):
        t=s.symbols('t',real=True);z=a+t*(b-a);u1,u2=z-v,w-v;r1,r2=ra-rv,rb-rv
        poly=s.factor(u1.dot(u2)**2*r1.dot(r1)*r2.dot(r2)-r1.dot(r2)**2*u1.dot(u1)*u2.dot(u2));good=[]
        for rt in s.solve(poly,t):
            if not 0<float(rt)<1:continue
            cand=simp(z.subs(t,rt))
            try:angle_eq(cand,v,w,ra,rv,rb)
            except AssertionError:continue
            good.append(cand)
        assert len(good)==1
        return good[0]
    X=angle_point(B,D,A,D,B,A,C);Y=angle_point(A,C,B,A,C,B,D)
    angle_eq(X,C,D,B,C,A);angle_eq(Y,D,A,C,D,B)
    O=center(A,B,C);eq(d2(D,O),d2(A,O))
    for a,b,c in ((A,B,C),(B,C,D),(C,D,A),(D,A,B)):pos(cross(b-a,c-b))
    return rec({'A':A,'B':B,'C':C,'D':D,'X':X,'Y':Y},
                    {'AB_squared':d2(A,B),'BC_squared':d2(B,C),'CD_squared':d2(C,D),'DA_squared':d2(D,A),'AC_squared':d2(A,C),'BD_squared':d2(B,D)},d2(X,Y))



def build():
    out={}
    # DB01: center height comes from the original product condition.
    scale=16*s.sqrt(14)/45
    A,B,C=V(0,s.sqrt(14)/2)*scale,V(-1,0)*scale,V(2,0)*scale
    O=center(A,B,C);k=s.symbols('k',real=True);J=V(0,k)
    P,Q=other(J,A,B-A),other(J,A,C-A)
    p=simp((P-A).dot(B-A)/d2(A,B));q=simp((Q-A).dot(C-A)/d2(A,C))
    kval=s.solve(p+q-1,k)[0];J=J.subs(k,kval);P=P.subs(k,kval);Q=Q.subs(k,kval)
    U=center(B,O,C);r1=positive_sqrt(d2(J,A));r2=positive_sqrt(d2(U,B));dist=positive_sqrt(d2(U,J))
    eq(r1,1);eq(r2,4);eq(dist,r1+r2)
    eq(d2(B,P)*d2(C,Q),d2(A,P)*d2(A,Q))
    for t in (p.subs(k,kval),q.subs(k,kval)):pos(t);pos(1-t)
    # A common outer tangent is built from a normal satisfying n.(U-J)=r1-r2.
    e=simp((U-J)/dist);perp=V(-e[1],e[0]);n=simp((r1-r2)/dist*e+s.sqrt(1-(r1-r2)**2/dist**2)*perp)
    Y=simp(J+r1*n);Z=simp(U+r2*n)
    eq(n.dot(Z-Y));eq(d2(Y,J),r1**2);eq(d2(Z,U),r2**2)
    out['DB01']=rec({'A':A,'B':B,'C':C,'O':O,'J':J,'P':P,'Q':Q,'U':U,'Y':Y,'Z':Z},
                    {'JA':r1,'UB':r2},positive_sqrt(d2(Y,Z)))

    # DB02: rotate the original angle rays; do not use the circumcircle conclusion.
    A,B,C=V(3,2*s.sqrt(10)),V(0,0),V(12,0)
    def rotate(u,co,si):return simp(V(co*u[0]-si*u[1],si*u[0]+co*u[1]))
    def trig(u,v):
        norm=s.sqrt(u.dot(u)*v.dot(v));return u.dot(v)/norm,abs(cross(u,v))/norm
    co,si=trig(A-C,B-C);P=line(A,A+rotate(B-A,co,si),B,C)
    co,si=trig(A-B,C-B);Q=line(A,A+rotate(C-A,co,-si),B,C)
    M,N=2*P-A,2*Q-A;X=line(B,M,C,N)
    angle_eq(P,A,B,B,C,A);angle_eq(C,A,Q,A,B,C)
    O=center(A,B,C);eq(d2(X,O),d2(A,O));eq(d2(B,X)*d2(A,C),d2(C,X)*d2(A,B))
    out['DB02']=rec({'A':A,'B':B,'C':C,'P':P,'Q':Q,'M':M,'N':N,'X':X},
                    {'AB':positive_sqrt(d2(A,B)),'AC':positive_sqrt(d2(A,C)),'BC':positive_sqrt(d2(B,C))},positive_sqrt(d2(B,X)))

    # DB03: input A is a chosen point on a 60-degree circle. Excenter and T are
    # reconstructed from it; the desired product relation is not used.
    B,C=V(0,0),V(7,0);O=V(R(7,2),7/(2*s.sqrt(3)))
    tangent_half=(4*s.sqrt(10)+5*s.sqrt(3))/17
    A=other(O,B,V(1-tangent_half**2,2*tangent_half)).applyfunc(lambda e:s.simplify(s.radsimp(e)))
    a,b,c=positive_sqrt(d2(B,C)),positive_sqrt(d2(A,C)),positive_sqrt(d2(A,B))
    Ib=((a*A-b*B+c*C)/(a-b+c)).applyfunc(lambda e:s.simplify(s.radsimp(e)));D=((b*B+c*C)/(b+c)).applyfunc(lambda e:s.simplify(s.radsimp(e)));M=other(O,A,D-A);T=other(O,M,Ib-M)
    TB,TC=positive_sqrt(d2(T,B)),positive_sqrt(d2(T,C))
    eq((B-A).dot(C-A),b*c/2);eq(TB+TC,13);eq(d2(B,C),49)
    angle_eq(T,B,Ib,T,Ib,C);angle_eq(T,C,Ib,T,Ib,B)
    out['DB03']=rec({'A':A,'B':B,'C':C,'I_b':Ib,'M':M,'T':T},
                    {'angle_BAC_degrees':60,'BC':a,'TB_plus_TC':TB+TC},positive_sqrt(d2(T,Ib)))

    # DB04: intersect two explicitly specified circles and their true bisectors.
    A=V(0,0);O1,O2=V(1,R(4,3)),V(4,R(-16,3));B=common(O1,O2,A)
    C=other(O2,A,V(-O1[1],O1[0]));D=other(O1,A,V(-O2[1],O2[0]))
    internal=simp(C/s.sqrt(C.dot(C))+D/s.sqrt(D.dot(D)))
    external=simp(C/s.sqrt(C.dot(C))-D/s.sqrt(D.dot(D)))
    E,F=other(O1,A,internal),other(O2,A,internal)
    X,Y=other(O1,A,external),other(O2,A,external);K=(X+Y)/2;U=center(B,E,F)
    radius=positive_sqrt(d2(U,E));eq(((U-K).dot(Y-X))**2,d2(U,E)*d2(X,Y))
    out['DB04']=rec({'A':A,'B':B,'C':C,'D':D,'E':E,'F':F,'X':X,'Y':Y,'K':K,'U':U,'O_1':O1,'O_2':O2},
                    {'EF':positive_sqrt(d2(E,F)),'AK':positive_sqrt(d2(A,K))},radius)

    out['DB06']=build_db06()

    # DB08: original projection and angle conditions, then the extra central secant.
    scale=9*s.sqrt(2)/10;A,B,C=V(0,3)*scale,V(-1,0)*scale,V(4,0)*scale
    O=center(A,B,C);tan=V(-(A-O)[1],(A-O)[0]);P=line(A,A+tan,B,C);X=foot(A,O,P)
    def ray_choice(base,a,v,b,l1,l2):
        co,si=trig(a-v,b-v);good=[]
        for sign in (1,-1):
            dr=rotate(base,co,sign*si);p=line(X,X+dr,l1,l2)
            if float(s.N((p-X).dot(dr)))>0 and float(s.N(cross(P-O,p-O)*cross(P-O,A-O)))>0:good.append(p)
        assert len(good)==1
        return good[0]
    E=ray_choice(P-X,A,C,X,A,B);F=ray_choice(O-X,A,B,X,A,C)
    angle_eq(E,X,P,A,C,X);angle_eq(F,X,O,A,B,X)
    t=s.symbols('t',real=True);z=E+t*(F-E);roots=s.solve(d2(z,O)-d2(A,O),t);assert len(roots)==2
    K,L=[simp(z.subs(t,rt)) for rt in roots];U=center(K,L,X);radius=positive_sqrt(d2(U,X))
    unit=simp((P-U)/s.sqrt(d2(P,U)));Y=simp(U+radius*unit);Z=simp(U-radius*unit)
    eq((U-X).dot(P-O));pos((Y-P).dot(U-P));pos((U-Y).dot(U-P));pos((Z-U).dot(U-P))
    out['DB08']=rec({'A':A,'B':B,'C':C,'O':O,'P':P,'X':X,'E':E,'F':F,'K':K,'L':L,'U':U,'Y':Y,'Z':Z},
                    {'PY':positive_sqrt(d2(P,Y)),'YZ':positive_sqrt(d2(Y,Z))},positive_sqrt(d2(P,X)))

    # DB09 remains a probe. Solve the defining angles before verifying complement.
    A=V(s.sqrt(5)*(3+s.sqrt(3))/6,(3+s.sqrt(3))/6);B,C=V(-1,0),V(1,0);M=(B+C)/2
    D,E=other(M,B,A-B),other(M,C,A-C)
    xx,yy=s.symbols('xx yy',real=True);p=V(xx,yy)
    def cotdiff(a,b,c,d):return s.expand(a.dot(b)*cross(c,d)-c.dot(d)*cross(a,b))
    sols=s.solve([cotdiff(p-B,A-B,p-A,C-A),cotdiff(p-C,A-C,p-A,B-A)],(xx,yy),dict=True);good=[]
    for sol in sols:
        cand=simp(p.subs(sol))
        if cand.free_symbols:continue
        signs=[cross(j-i,cand-i)*cross(j-i,k-i) for i,j,k in ((A,B,C),(B,C,A),(C,A,B))]
        if all(float(s.N(k))>0 for k in signs):good.append(cand)
    assert len(good)==1;P=good[0];angle_eq(P,B,A,P,A,C);angle_eq(P,C,A,P,A,B)
    eq(4*d2(P,M)*d2(D,E),d2(B,C)**2)
    t=s.symbols('t',real=True);z=M+t*(P-A);roots=s.solve(d2(z,B)*d2(A,C)-d2(z,C)*d2(A,B),t)
    good=[]
    for rt in roots:
        cand=simp(z.subs(t,rt))
        if float(s.N(d2(cand,M)-1))>0 and float(s.N(cand[1]))>0:good.append(cand)
    assert len(good)==1;X=good[0]
    coA=simp((B-A).dot(C-A)/s.sqrt(d2(A,B)*d2(A,C)));coX=simp((B-X).dot(C-X)/s.sqrt(d2(X,B)*d2(X,C)))
    eq(coA,s.sqrt(3)/2);eq(coX,R(1,2))
    out['DB09']=rec({'A':A,'B':B,'C':C,'M':M,'D':D,'E':E,'P':P,'X':X},{'angle_BAC_degrees':30,'BC':2},60)

    # DB10: radical center is solved from powers, not placed on the median.
    scale=s.sqrt(31/(6*s.sqrt(3)));A,B,C=V(0,0),V(4,0)*scale,V(3,3*s.sqrt(3))*scale
    K,L=V(2,-2*s.sqrt(3))*scale,V(-3,3*s.sqrt(3))*scale
    S=line(C,K,A,B);Rr=line(B,L,A,C);T=line(B,L,C,K);M=(B+C)/2
    centers=[center(B,S,K),center(C,L,Rr),center(B,T,C)];radii=[d2(o,p) for o,p in zip(centers,[B,C,B], strict=False)]
    xx,yy=s.symbols('xx yy');z=V(xx,yy);powers=[s.expand(d2(z,o)-r) for o,r in zip(centers,radii, strict=False)]
    sol=s.solve([powers[0]-powers[1],powers[1]-powers[2]],(xx,yy));Z=simp(z.subs(sol));eq(cross(Z-A,M-A))
    areaABC=abs(cross(B-A,C-A))/2;areaAZB=abs(cross(Z-A,B-A))/2
    ratio=positive_sqrt(d2(A,Z)/d2(Z,M));eq(ratio,R(12,19))
    out['DB10']=rec({'A':A,'B':B,'C':C,'K':K,'L':L,'S':S,'R':Rr,'T':T,'M':M,'Z':Z},
                    {'area_ABC':areaABC,'AZ_over_ZM':ratio},areaAZB)

    # DB12: two parallel-grid circles, intersected without the fixed-point formula.
    A,B,C=V(-s.sqrt(30),-s.sqrt(30)),V(5,0),V(0,12)
    def grid(t):
        D=B+t*(C-B);E=line(D,D+B-A,A,C);F=line(D,D+C-A,A,B)
        return D,E,F,center(A,E,F)
    D1,E1,F1,U1=grid(R(1,3));D2,E2,F2,U2=grid(R(2,3));X=common(U1,U2,A)
    coA=simp((B-A).dot(C-A)/s.sqrt(d2(A,B)*d2(A,C)));eq(coA,s.sqrt(2)/2)
    BX,CX=positive_sqrt(d2(B,X)),positive_sqrt(d2(C,X));eq(BX+CX,17)
    out['DB12']=rec({'A':A,'B':B,'C':C,'D_1':D1,'E_1':E1,'F_1':F1,'D_2':D2,'E_2':E2,'F_2':F2,'X':X},
                    {'angle_BAC_degrees':45,'BC':positive_sqrt(d2(B,C)),'BX_plus_CX':BX+CX},positive_sqrt(d2(A,X)))

    # DB13: solve the internal tangency equation of the circle through E,F.
    A,B,C=V(0,12),V((9-s.sqrt(561))/2,0),V((9+s.sqrt(561))/2,0)
    O=center(A,B,C);E,F=(A+C)/2,(A+B)/2;G=(A+B+C)/3;P=foot(A,B,C)
    w=s.symbols('w',real=True);W=V((E[0]+F[0])/2,w);r2=d2(E,W);R2=d2(A,O);dd=d2(W,O)
    roots=s.solve(s.factor((R2+r2-dd)**2-4*R2*r2),w);good=[]
    for rt in roots:
        u=simp(W.subs(w,rt));r=d2(u,E);d=d2(u,O)
        if abs(float(s.N(s.sqrt(d)+s.sqrt(r)-s.sqrt(R2))))>1e-9:continue
        p=simp(O+s.sqrt(R2/d)*(u-O))
        if d2(p,A)!=0:good.append((u,p))
    assert len(good)==1;W,Rr=good[0]
    eq(cross(G-P,Rr-P));pos(-cross(C-B,Rr-B)*cross(C-B,A-B))
    area_ratio=simp(abs(cross(B-Rr,C-Rr))/abs(cross(B-A,C-A)))
    out['DB13']=rec({'A':A,'B':B,'C':C,'O':O,'E':E,'F':F,'G':G,'P':P,'W':W,'R':Rr},
                    {'PG':positive_sqrt(d2(P,G)),'GR':positive_sqrt(d2(G,Rr))},area_ratio)

    # DB15: Q comes from the original squared-side-ratio chord; T is intersected.
    A,B,C=V(-2,-2*s.sqrt(6)),V(8,2*s.sqrt(6)),V(-4,2*s.sqrt(6));D=foot(A,B,C);E,F=(A+C)/2,(A+B)/2
    S=simp((d2(A,C)*B+d2(A,B)*C)/(d2(A,B)+d2(A,C)));O=center(A,B,C);L=other(O,A,S-A);Q=(A+L)/2;T=line(D,Q,E,F)
    out['DB15']=rec({'A':A,'B':B,'C':C,'D':D,'E':E,'F':F,'S':S,'L':L,'Q':Q,'T':T},
                    {'DE':positive_sqrt(d2(D,E)),'DF':positive_sqrt(d2(D,F)),'EF':positive_sqrt(d2(E,F))},positive_sqrt(d2(D,T)))

    # DB16: P is on the ray AS (source allows this), not necessarily the segment.
    A=V(0,0);B=V(R(135,124),129*s.sqrt(15)/124);C=V(R(-135,184),159*s.sqrt(15)/184);P=V(0,3*s.sqrt(15)/2)
    O=center(A,B,C);O1,O2=center(A,P,B),center(C,A,P);N=line(A,O,O1,O2)
    S=simp((d2(A,C)*B+d2(A,B)*C)/(d2(A,B)+d2(A,C)))
    eq(cross(P-A,S-A));pos((P-A).dot(S-A));eq(d2(N,O1),d2(N,O2))
    out['DB16']=rec({'A':A,'B':B,'C':C,'S':S,'P':P,'O':O,'O_1':O1,'O_2':O2,'N':N},
                    {'AO_1':positive_sqrt(d2(A,O1)),'AO_2':positive_sqrt(d2(A,O2)),'O_1O_2':positive_sqrt(d2(O1,O2))},positive_sqrt(d2(A,N)))
    return out


def check_general_relations():
    """Symbolic identities support the researcher-only lemmas, not the witness
    generation. Variables remain free. Positivity/domain conditions stated in
    the cards select the ordinary-angle and internal-tangency branches.
    """
    # DB01. Normalize acute ABC to A=(0,h), B=(-u,0), C=(v,0), h²>uv.
    # The product condition gives AP/AB+AQ/AC=1 and thus the displayed r.
    u,v,h=s.symbols('u v h',positive=True);A,B,C=V(0,h),V(-u,0),V(v,0)
    O=V((v-u)/2,(h*h-u*v)/(2*h));prod=(h*h+u*u)*(h*h+v*v)
    r=prod/(2*h*(2*h*h+u*u+v*v));Rr=prod/(4*h*(h*h-u*v));J=V(0,h-r);U=center(B,O,C)
    eq(d2(J,U),(r+Rr)**2)  # both radii positive: external tangency.

    # DB02. Unnormalized rotation coefficients avoid unnecessary square roots.
    c,h=s.symbols('c h',positive=True);A,B,C=V(0,h),V(-1,0),V(c,0)
    def rot(v,co,si):return V(co*v[0]-si*v[1],si*v[0]+co*v[1])
    pdir=rot(B-A,(A-C).dot(B-C),cross(A-C,B-C))
    qdir=rot(C-A,(A-B).dot(C-B),cross(A-B,C-B))
    P=line(A,A+pdir,B,C);Q=line(A,A+qdir,B,C);M,N=2*P-A,2*Q-A;X=line(B,M,C,N);O=center(A,B,C)
    eq(d2(X,O),d2(A,O));eq(d2(B,X)*d2(A,C),d2(C,X)*d2(A,B))

    # DB04. Internal/external bisectors are the axes. The two center directions
    # force O1=(e/2,ke/2), O2=(f/2,-kf/2), e,f,k>0, e!=f.
    e,f,k=s.symbols('e f k',positive=True);A=V(0,0);O1,O2=V(e/2,k*e/2),V(f/2,-k*f/2)
    B=common(O1,O2,A);E,F=V(e,0),V(f,0);K=V(0,k*(e-f)/2);U=center(B,E,F)
    eq((U[1]-K[1])**2,d2(U,E))

    # DB08. c>1 expresses AC>AB; h²>c makes A acute. The two rotations below
    # have positive ray parameters and lie on the A side of OP in that domain.
    c,h=s.symbols('c h',positive=True);A,B,C=V(0,h),V(-1,0),V(c,0);O=center(A,B,C)
    P=line(A,A+V(-(A-O)[1],(A-O)[0]),B,C);X=foot(A,O,P)
    def angular_intersection(base,a,b,end):
        co,det=a.dot(b),cross(a,b)
        return line(X,X+V(co*base[0]+det*base[1],-det*base[0]+co*base[1]),A,end)
    E=angular_intersection(P-X,A-C,X-C,B);F=angular_intersection(O-X,A-B,X-B,C)
    norm=V(E[1]-F[1],F[0]-E[0]);c0=-norm.dot(E)
    lam=s.factor(-(d2(X,O)-d2(A,O))/(norm.dot(X)+c0));U=simp(O-lam*norm/2)
    # Adding lam*(line EF) to Gamma's equation produces the circle through K,L,X.
    eq((U-X).dot(P-O))

    # DB10. Fully variable adjacent sides b,c; compute three circumcircles and
    # their radical center before checking the median, rather than inserting it.
    b,c=s.symbols('b c',positive=True);A=V(0,0);B=V(c,0);C=V(b/2,s.sqrt(3)*b/2)
    K,L=V(c/2,-s.sqrt(3)*c/2),V(-b/2,s.sqrt(3)*b/2)
    S=line(C,K,A,B);RR=line(B,L,A,C);T=line(B,L,C,K)
    cc=[center(B,S,K),center(C,L,RR),center(B,T,C)];rr=[d2(o,p) for o,p in zip(cc,[B,C,B], strict=False)]
    xx,yy=s.symbols('xx yy');Z=V(xx,yy);power=[s.expand(d2(Z,o)-r) for o,r in zip(cc,rr, strict=False)]
    sol=s.solve([power[0]-power[1],power[1]-power[2]],(xx,yy));Z=Z.subs(sol);M=(B+C)/2
    eq(cross(Z,M));eq(Z[0]/M[0],2*b*c/(b*b+3*b*c+c*c))

    # DB13. Solve the actual tangency equation for the circle through E,F.
    c,h=s.symbols('c h',positive=True);A,B,C=V(0,h),V(-1,0),V(c,0)
    O=center(A,B,C);E,F=(A+C)/2,(A+B)/2;G=(A+B+C)/3;R2=d2(A,O)
    w=s.symbols('w');W=V((c-1)/4,w);r2=d2(W,E);dd=d2(W,O)
    roots=s.solve(s.factor((R2+r2-dd)**2-4*R2*r2),w);found=0
    for rt in roots:
        if simp(rt-(A[1]+O[1])/2)==0:continue  # the circle tangent at A.
        ww=simp(W.subs(w,rt));r2=d2(ww,E);dd=d2(ww,O)
        contact=simp(O+(R2-r2+dd)/(2*dd)*(ww-O))
        eq(d2(contact,O),R2);eq(d2(contact,ww),r2);eq(cross(G,contact));found+=1
    assert found==1

    # DB16. All nondegenerate triangles rotate/scale to A=0, B=(c,0), C=(x,y).
    c,x,y,t=s.symbols('c x y t',nonzero=True);A=V(0,0);B=V(c,0);C=V(x,y)
    S=((x*x+y*y)*B+c*c*C)/(x*x+y*y+c*c);P=t*S;O=center(A,B,C)
    O1,O2=center(A,P,B),center(C,A,P);N=(O1+O2)/2
    eq(cross(O,N))
    return ['DB01','DB02','DB04','DB08','DB10','DB13','DB16']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--json',action='store_true');parser.add_argument('--only',choices=['DB06']);args=parser.parse_args()
    general_ids=[] if args.only else check_general_relations()
    values={'DB06':build_db06()} if args.only=='DB06' else build()
    path=Path(__file__).with_name('db_revision.json')
    if path.exists():
        for card in json.loads(path.read_text()):
            if card['decision'] not in ('main','probe'):continue
            key=card['id']
            if key not in values:continue
            eq(s.sympify(values[key]['answer']),s.sympify(card['answer_exact']))
            for given in card['givens']:
                assert given['name'] in values[key]['given_values'],(key,given['name'])
                eq(s.sympify(given['value']),s.sympify(values[key]['given_values'][given['name']]))
    if args.json:print(json.dumps(values,ensure_ascii=False,indent=2))
    else:print('PASS: '+str(len(values))+' original-construction witnesses; all givens/answers checked; '+str(len(general_ids))+' general symbolic identities checked.')

if __name__=='__main__':main()
