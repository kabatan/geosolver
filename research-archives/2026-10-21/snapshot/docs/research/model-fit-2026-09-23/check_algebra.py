"""Audit a claimed generic elimination; never sent to the actor models."""
import json
from pathlib import Path
import sympy as s
p,q=s.symbols('p q',real=True)
K=p*p+q*q;den=K+24*p+144
Dx=12*(K+12*p)/den;Dy=144*q/den
md2=s.factor((Dx-6)**2+Dy**2)
expected=36*(K-24*p+144)/den
checks=[{'name':'DA05 MD squared generic identity','pass':s.factor(md2-expected)==0},
 {'name':'DA05 MD4 constraint','pass':s.factor((md2-16)*den-4*(5*K-312*p+720))==0},
 {'name':'DA05 concrete acute scalene witness MD4','pass':s.simplify(md2.subs({p:4,q:s.sqrt(s.Rational(448,5))})-16)==0},
 {'name':'2507 incorrect constraint fails at witness','pass':s.Rational(448,5)!=48*4-144}]
assert all(x['pass'] for x in checks)
S=s.Point(0,0);U=s.Point(4,0);V=s.Point(9,0);T=s.Point(s.Rational(72,13),s.Rational(30,13));O=s.Point(s.Rational(13,2),0)
checks += [{'name':'B06 witness T on circle','pass':s.simplify(T.distance(O)**2-s.Rational(25,4))==0},
 {'name':'B06 ST tangent','pass':s.simplify(s.Matrix(T-S).dot(s.Matrix(T-O)))==0},
 {'name':'B06 stated original wrong ratio fails','pass':T.distance(S)/U.distance(S)!=U.distance(S)/V.distance(S)}]
assert all(x['pass'] for x in checks)
Path(__file__).with_name('algebra-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print(len(checks),'checks passed')
