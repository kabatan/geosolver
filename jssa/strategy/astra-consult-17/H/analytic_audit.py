"""Exact analysis of two singular cases and the auxiliary-point exception.

No search and no changes to the preregistered numerical outputs.
"""
import json
from pathlib import Path

import numpy as np
import sympy as sp

HERE=Path(__file__).resolve().parent


def shape(figure,names):
    points=np.asarray([figure[n] for n in names])
    distances=np.array([np.sum((points[i]-points[j])**2)
        for i in range(len(points)) for j in range(i+1,len(points))])
    return distances/distances.sum()


def main():
    # AIME 2018 II 14: u=semiperimeter-BC, A=(0,0),B=(7,0),C=(c,h).
    u=sp.symbols('u')
    a=15-2*u
    c=(113-a*a)/14
    h2=64-c*c
    r_over_h=u/(8+c)
    Xx=7+(7-u)/a*(c-7)
    Xy_over_h=(7-u)/a
    AX2=sp.factor(Xx*Xx+h2*Xy_over_h*Xy_over_h)
    # The two intersections of AX with the incircle are X and tY*X.
    tY=sp.factor(u*u/AX2)
    Yx=tY*Xx
    Yy_over_h=tY*Xy_over_h
    # Tangent at Y contains P=(3,0): (Y-I).(P-I)=r^2.
    tangent=sp.factor((3-u)*Yx-h2*r_over_h*Yy_over_h-3*u+u*u)
    expected=4*u*(u-8)*(u-7)*(5*u-21)/(7*(2*u*u-45*u+224))
    assert sp.cancel(tangent-expected)==0
    q_fraction=sp.factor(3*Yy_over_h/(c*Yy_over_h-Yx+3))
    chosen=sp.Rational(21,5)
    assert sp.simplify(q_fraction.subs(u,chosen))==sp.Rational(21,59)
    assert sp.simplify(c.subs(u,chosen))==sp.Rational(124,25)
    result={'AIME-2018-II-14':{
        'method':'exact real geometry; see analytic-notes.md',
        'u':'semiperimeter-BC', 'interval':'0 < u < 7',
        'tangent_numerator':str(sp.factor(sp.fraction(tangent)[0])),
        'tangent_denominator':str(sp.factor(sp.fraction(tangent)[1])),
        'only_admissible_u':str(chosen),
        'Q_fraction_of_AC':str(q_fraction.subs(u,chosen)),
        'target':str(8*q_fraction.subs(u,chosen)),
        'real_dimension':0,'exact_check':True}}

    v=sp.symbols('v')
    assert sp.expand(sp.Rational(4,3)*(v*v+3*u*u)-(u+v)**2-(v-3*u)**2/3)==0
    result['AIME-2008-I-10']={
        'method':'real inequalities plus equality case; see analytic-notes.md',
        'upper_bound_identity':'4*(v^2+3*u^2)/3-(u+v)^2=(v-3*u)^2/3',
        'd_lower_bound':'20*sqrt(7) from reverse triangle inequality',
        'unique_x':['20*sqrt(7)','5*sqrt(7)','15*sqrt(7)','-10*sqrt(7)','0'],
        'target':'25*sqrt(7)','real_dimension':0,'exact_check':True}

    d=json.loads((HERE/'diagnostic/AIME-2015-II-11.json').read_text())
    names=[n for n in d['point_names'] if n!='V']
    base=shape(d['figure'],names)
    maximum=max(float(np.max(np.abs(shape(q['figure'],names)-base)))
                for q in d['samples'] if q['accepted'])
    result['AIME-2015-II-11']={
        'method':'remove the point used only to represent line OV',
        'names_retained':names,'max_shape_change_without_V':maximum,
        'max_shape_change_with_V':d['max_shape_change'],
        'interpretation':'V slides on the same line; no physical shape freedom'}

    A=sp.Matrix([0,0]); B=sp.Matrix([180,0])
    C=sp.Matrix([sp.Rational(98398,361),sp.Rational(31416,361)*sp.sqrt(2)])
    D=sp.Matrix([98,56*sp.sqrt(2)])
    points=[A,B,C,D]
    squared=lambda vector:sp.simplify(vector.dot(vector))
    cross=lambda a,b:sp.factor(a[0]*b[1]-a[1]*b[0])
    lengths=[sp.sqrt(squared(points[(i+1)%4]-points[i])) for i in range(4)]
    turns=[cross(points[(i+1)%4]-points[i],points[(i+2)%4]-points[(i+1)%4]) for i in range(4)]
    assert lengths==[180,154,180,126]
    assert all(v>0 for v in turns)
    assert sp.simplify((D-A).dot(B-A)/(126*180))==sp.Rational(7,9)
    assert sp.simplify((B-C).dot(D-C)/(154*180))==sp.Rational(7,9)
    result['aime-2003-1-12']={'method':'exact existence witness for new certificate',
        'points':{name:list(map(str,p)) for name,p in zip('ABCD',points)},
        'edge_lengths':list(map(str,lengths)),'positive_turns':list(map(str,turns)),
        'both_angle_cosines':'7/9','exact_check':True}
    (HERE/'analytic-audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=='__main__': main()
