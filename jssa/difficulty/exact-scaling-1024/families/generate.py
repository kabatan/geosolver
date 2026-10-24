"""Generate three exact-depth families; all share one free scalar t as output."""
import argparse
import json
from pathlib import Path
import sys

import sympy as sp
from mpmath import mp

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from collect_real import features

FAMILIES = ('circle_line', 'angle_bisector', 'midpoint_control')


def construction(name, expression):
    return dict(name=name,expression=expression)


def make(family, k):
    cid=f'{family}-k{k}'
    if family=='circle_line':
        commands=[construction('O','Point(0, 0)'),construction('U','Point(0, 1)'),construction('P0','Point(0, 0)')]
        for i in range(1,k+1):
            p=f'P{i-1}'
            commands.append(construction(f'P{i}',
                f'Intersect(Line(O, U), Circle(Point((1 + {p}.y)/2, 0), (3 + {p}.y)/2), near=Point(0, 3))'))
        target=f'P{k}.y'
        text=(f'O=(0,0)、U=(0,1)、P0=Oとする。i=1,…,{k}について、a=2+P(i−1)のy座標と置く。'
              '中心((a−1)/2,0)、半径(a+1)/2の円と直線OUの交点のうち、(0,3)に近い方をPiとする。'
              f'Pkのy座標 t を求めよ。ここでk={k}。')
    elif family=='angle_bisector':
        commands=[construction('O','Point(0, 0)'),construction('A','Point(1, 0)'),construction('B0','Point(1, 1)')]
        for i in range(1,k+1):
            commands.append(construction(f'B{i}',f'Intersect(AngleBisector(A, O, B{i-1}), Line(A, B0))'))
        target=f'B{k}.y'
        text=(f'O=(0,0)、A=(1,0)、B0=(1,1)とする。i=1,…,{k}について、角AOB(i−1)の内角二等分線と'
              f'直線x=1の交点をBiとする。Bkのy座標 t を求めよ。ここでk={k}。')
    elif family=='midpoint_control':
        commands=[construction('O','Point(0, 0)'),construction('P0','Point(1, 0)')]
        for i in range(1,k+1):
            commands.append(construction(f'P{i}',f'Midpoint(O, P{i-1})'))
        target=f'P{k}.x'
        text=(f'O=(0,0)、P0=(1,0)とする。i=1,…,{k}について、OとP(i−1)の中点をPiとする。'
              f'Pkのx座標 t を求めよ。ここでk={k}。')
    else:
        raise ValueError(family)
    dsl=dict(id=cid,variables=['t'],constructions=commands,
             conditions=[dict(left='t',operator='=',right=target)],target='t')
    f,trace=features(dsl)
    assert f['depth']==k and f['point_depth']==k
    return dsl,text,f,trace


def certificate(family,k):
    T=sp.Symbol('T')
    mp.dps=220
    if family=='circle_line':
        poly=sp.Poly(T,T)
        for _ in range(k):
            poly=sp.Poly(poly.as_expr().subs(T,T*T-2).expand(),T)
        c=[int(x) for x in poly.all_coeffs()]
        eisenstein=all(x%2==0 for x in c[1:]) and c[-1]%4!=0 and c[0]%2!=0
        assert eisenstein
        value=2*mp.cos(mp.pi/(2**(k+1)))
        proof='P0(T)=T; Pi(T)=P(i-1)(T^2-2). Each Pi is 2-Eisenstein, hence irreducible of degree 2^i.'
        finite=('At each stage x_i=0 and y_i^2=2+y_(i-1), y0=0. '
                'Each predecessor lies in (-2,2), so two distinct nonzero real algebraic roots exist; '
                'circle radius (3+y_(i-1))/2>0. The near=(0,3) selector uniquely chooses the positive root. '
                'Previous coordinates are recovered by y_(i-1)=y_i^2-2. Thus 2^k relaxed configurations, one selected configuration.')
    elif family=='angle_bisector':
        n=2**k
        # Re((1+iT)^n) - Im((1+iT)^n) = 0.
        expr=sum(sp.binomial(n,j)*(-1)**(j//2)*(1 if j%2==0 else -1)*T**j for j in range(n+1))
        poly=sp.Poly(expr,T).monic()
        # Cyclotomic X^(2n)+1 is irreducible: translation X -> X+1 is 2-Eisenstein.
        eisenstein=all(int(sp.binomial(2*n,j))%2==0 for j in range(1,2*n))
        assert eisenstein
        value=mp.tan(mp.pi/(4*n))
        proof=('Let n=2^k, theta=pi/(4n), zeta=exp(2i theta). '
               'zeta has irreducible polynomial X^(2n)+1 (its shift by 1 is 2-Eisenstein), hence degree 2n. '
               'i=zeta^n; t=-i(zeta-1)/(zeta+1) is real, and zeta=(1+it)/(1-it). '
               'Q(zeta)=Q(t,i), [Q(t,i):Q(t)]=2, so [Q(t):Q]=n. '
               'The displayed degree-n polynomial vanishes by tan(n theta)=1 and is therefore minimal.')
        finite=('The selected slopes obey y0=1, s_i=sqrt(1+y_(i-1)^2)>0, '
                'y_i=y_(i-1)/(1+s_i)=tan(pi/2^(i+2)). '
                'For the relaxed equations both square-root signs give 2^k distinct real slopes; '
                'the inverse y_(i-1)=2*y_i/(1-y_i^2) recovers all preceding coordinates. '
                'No conjugate equals 0, +/-1 or +/-i, so all line/angle nonzero factors and denominators stay nonzero. '
                'The genuine interior bisectors define one configuration.')
    else:
        poly=sp.Poly(2**k*T-1,T)
        eisenstein=None
        value=mp.mpf(1)/(2**k)
        proof='t=1/2^k is rational; primitive minimal polynomial 2^k*T-1 has degree 1.'
        finite='Every midpoint is uniquely determined; the sole free scalar is fixed by t=P_k.x. One complex and one real configuration.'
    coeffs=[str(c) for c in poly.all_coeffs()]
    residual=mp.mpf(0)
    for c in coeffs:
        residual=residual*value+mp.mpf(c)
    assert abs(residual)<mp.mpf('1e-100'),(family,k,residual)
    return dict(family=family,k=k,target='t',minimal_polynomial=str(poly.as_expr()),
                coefficient_order='descending',coefficients=coeffs,degree=poly.degree(),
                proof=proof,eisenstein_check=eisenstein,finiteness_proof=finite,
                intended_target_100_digits=mp.nstr(value,100),
                polynomial_residual_at_220_digits=str(residual),
                selected_real_target_count=1,relaxed_complex_configuration_count=poly.degree(),
                status='PROVED_EXACTLY',numeric_check_role='sanity only; not the irreducibility/finite-degree proof')


def write_one(family,k,reuse=False):
    dsl,text,f,trace=make(family,k)
    directory=HERE/family
    directory.mkdir(parents=True,exist_ok=True)
    inp=directory/f'k{k}.json'
    if inp.exists():
        if not reuse:
            raise RuntimeError('No implicit overwrite: '+str(inp))
        assert json.loads(inp.read_text())==dsl
        cert=json.loads((directory/f'k{k}-minpoly.json').read_text())
        return inp,cert,f
    inp.write_text(json.dumps(dsl,ensure_ascii=False,indent=2)+'\n')
    cert=certificate(family,k)
    (directory/f'k{k}-minpoly.json').write_text(json.dumps(cert,ensure_ascii=False,indent=2)+'\n')
    (directory/f'k{k}-depth.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2)+'\n')
    (directory/f'k{k}.md').write_text(f'# {family}, k={k}\n\n{text}\n\n'
        'DSLでは自由スカラーtを1つ置き、作図の最後の座標との等式で固定する。'
        '最小多項式と有限性の根拠は同名の `-minpoly.json` に収録。\n')
    return inp,cert,f


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('family',choices=FAMILIES)
    ap.add_argument('k',type=int)
    a=ap.parse_args()
    path,cert,_=write_one(a.family,a.k)
    print(path,cert['degree'])
