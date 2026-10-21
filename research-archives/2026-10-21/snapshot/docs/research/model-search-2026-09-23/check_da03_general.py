"""Auditor-side generic identity check. Never supplied to any tested model."""
import json
from pathlib import Path
import sympy as s
u,v=s.symbols('u v',real=True,nonzero=True)
S=u*u+v*v;k=(S-2*u)/(2*v)  # B=(0,0), C=(2,0), A=(u,v), O=(1,k)
d=-(4+S)/2;e=(-2*S-d*u)/v;e2=(1-k*k)/k
# Circle1: x²+y²+d*x+e*y+S=0; circle2: x²+y²-2*x+e2*y=0.
# Their radical axis through C has direction (1,l).
l=s.factor(S/(2*(e-e2)));t=s.factor(-(2+e2*l)/(1+l*l))
tx=s.factor(2+t);ty=s.factor(l*t)
xk=s.factor((tx*k-ty)/(k-ty))
checks={'circle1_contains_A':s.factor(S+d*u+e*v+S)==0,
 'circle1_contains_C':s.factor(4+2*d+S)==0,
 'circle1_tangent_AB_at_A':s.factor((2*u+d)*u+(2*v+e)*v)==0,
 'circle2_contains_O':s.factor(1+k*k-2+e2*k)==0,
 'T_circle1':s.factor(tx*tx+ty*ty+d*tx+e*ty+S)==0,
 'T_circle2':s.factor(tx*tx+ty*ty-2*tx+e2*ty)==0,
 'K_formula':s.factor(xk-S/(2*(u-1)))==0,
 'AK2_equals_KB_times_KC':s.factor((u-xk)**2+v*v-xk*(xk-2))==0}
assert all(checks.values())
out={'checks':checks,'K':str(xk),'scope':'Generic nondegenerate case with displayed denominators nonzero; independent algebraic check of reference relation, not a model answer or formal all-case proof.','training_eligible':False}
Path(__file__).with_name('da03-reference-check.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
