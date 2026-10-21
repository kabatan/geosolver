#!/usr/bin/env python3
"""Definition-first exact checks for DU01; no GPU or model calls."""
import argparse
import json

import sympy as s

R=s.Rational
V=lambda x,y:s.Matrix([s.sympify(x),s.sympify(y)])

def simp(x):
    return x.applyfunc(s.factor) if isinstance(x,s.MatrixBase) else s.factor(x)

def eq(a,b=0):
    z=simp(a-b)
    assert z==s.zeros(*z.shape) if isinstance(z,s.MatrixBase) else z==0, str(z)

def norm(x): return simp(x.dot(x))
def cross(x,y): return s.det(s.Matrix.hstack(x,y))

def line(a,b,c,d):
    return simp(a+cross(c-a,d-c)/cross(b-a,d-c)*(b-a))

def circle_center(a,b,c):
    matrix=s.Matrix.vstack((2*(b-a)).T,(2*(c-a)).T)
    return simp(matrix.inv()*V(norm(b)-norm(a),norm(c)-norm(a)))

def tangent_circle_center(a,b,tangent_direction):
    matrix=s.Matrix.vstack((b-a).T,tangent_direction.T)
    return simp(a+matrix.inv()*V(norm(b-a)/2,0))

def construct(A,B,C):
    U=tangent_circle_center(A,B,C-A)
    W=tangent_circle_center(A,C,B-A)
    # Radical axis through their known common point A, then solve its
    # intersection with the first original circle; do not assume symmedian.
    normal=U-W
    direction=V(-normal[1],normal[0])
    D=simp(A-2*(A-U).dot(direction)/norm(direction)*direction)
    O=circle_center(A,B,C)
    # Each tangent is defined by the radius perpendicular at its own point.
    K=simp(s.Matrix.vstack((B-O).T,(C-O).T).inv()*
           V((B-O).dot(B),(C-O).dot(C)))
    for P,Q in [(A,U),(B,U),(D,U)]:eq(norm(P-Q),norm(A-U))
    for P,Q in [(A,W),(C,W),(D,W)]:eq(norm(P-Q),norm(A-W))
    eq((U-A).dot(C-A));eq((W-A).dot(B-A))
    eq((K-B).dot(B-O));eq((K-C).dot(C-O))
    eq(cross(D-A,K-A))
    eq((U-W).dot(K-A))
    # Verification of Dumpty identity only after original construction.
    L=simp(A-2*(A-O).dot(D-A)/norm(D-A)*(D-A))
    eq(L,2*D-A)
    return {'A':A,'B':B,'C':C,'U':U,'V':W,'O':O,'D':D,'K':K,'L':L}

def fmt(x):
    if isinstance(x,dict): return {k:fmt(v) for k,v in x.items()}
    if isinstance(x,list|tuple|s.MatrixBase): return [fmt(v) for v in x]
    return s.sstr(x)

def run():
    b,c,t=s.symbols('b c t',positive=True)
    q=(1-t*t)/(1+t*t);h=2*t/(1+t*t)
    general=construct(V(0,0),V(c,0),V(b*q,b*h))
    expected_direction=V(b+c*q,c*h)
    expected_denominator=b*b+c*c+2*b*c*q
    eq(general['D'],b*c/expected_denominator*expected_direction)
    eq(general['K'],expected_direction/(2*q))
    basis=s.Matrix.hstack(general['B'],general['C'])
    d_coeff=simp(basis.inv()*general['D'])
    k_coeff=simp(basis.inv()*general['K'])
    eq(d_coeff,V(b*b/expected_denominator,c*c/expected_denominator))
    eq(k_coeff,V(b/(2*c*q),c/(2*b*q)))
    eq(1-sum(d_coeff),2*b*c*q/expected_denominator)
    eq(sum(k_coeff)-1,((b-c)**2+2*b*c*(1-q))/(2*b*c*q))
    # For 0<t<1, q>0: D has positive B,C barycentric coefficients
    # summing to (b²+c²)/(b²+c²+2bcq)<1.  K coefficients are positive
    # and sum to (b²+c²)/(2bcq)>1.  Thus both rays are internal and
    # K is beyond BC.  Acute B,C further require c>bq and b>cq.
    p=construct(V(0,0),V(4,0),V(3,4))
    A,B,C,U,W,O,D,K=[p[k] for k in ['A','B','C','U','V','O','D','K']]
    for P,Q,T in [(A,B,C),(B,A,C),(C,A,B)]:
        assert (Q-P).dot(T-P)>0
    assert norm(A-B)!=norm(A-C)
    assert norm(U-W)>0 and norm(D-A)>0
    S=line(A,D,B,C);T=line(A,K,B,C)
    eq(S,T)
    lam=simp((S-B).dot(C-B)/norm(C-B));assert 0<lam<1
    eq(lam/(1-lam),norm(A-B)/norm(A-C))
    assert cross(C-B,A-B)*cross(C-B,K-B)<0
    eq(norm(K-B),norm(K-C))
    return {'general_symbolic_checks':'PASS',
            'general_D':fmt(general['D']), 'general_K':fmt(general['K']),
            'domain':'b,c>0; 0<t<1; q=(1-t²)/(1+t²); c>bq and b>cq; b!=c',
            'witness':{'points':fmt(p|{'S':S}),
                       'BS_over_SC':fmt(lam/(1-lam)),
                       'UV_dot_AK':fmt((U-W).dot(K-A))}}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--json',action='store_true')
    args=parser.parse_args();result=run()
    print(json.dumps(result,ensure_ascii=False,indent=2) if args.json else
          'PASS: DU01 general incidence, perpendicularity, Dumpty midpoint identity, and exact acute witness/branches.')
