"""Exact checks for audit-sensitive formulas and counterexamples (CPU only)."""
import json
from pathlib import Path
import sympy as s
D=Path(__file__).resolve().parent
checks={}
c,d,e=s.symbols('c d e',positive=True)
S=d*d+e*e
DA=s.Matrix([-c*d*d/S,-c*d*e/S])
DE=s.Matrix([d-c*d*d/S,-c*d*e/S])
checks['F04_DA_dot_DE']=str(s.simplify(DA.dot(DE)-c*d*d*(c-d)/S))
checks['F04_DA_norm2']=str(s.simplify(DA.dot(DA)-c*c*d*d/S))
checks['F04_DE_norm2']=str(s.simplify(DE.dot(DE)-d*d*((c-d)**2+e*e)/S))
def cyclic_det(points):return s.det(s.Matrix([[x*x+y*y,x,y,1] for x,y in points]))
checks['F11_noncyclic_det']=str(cyclic_det([(0,2),(-1,0),(1,0),(0,-2)]))
checks['C14_noncyclic_det']=str(cyclic_det([(0,0),(2,1),(4,0),(2,-3)]))
t=s.symbols('t',real=True)
# Circle C=(c,sqrt(1-c²)); both tangent intersections.
checks['C05_tangent_dot']=str(s.simplify(-1+(1+t)*(1-t)/(1-t*t)))
A=s.Point(s.sqrt(3),1);B=s.Point(0,0);C=s.Point(s.sqrt(3)+1,0);F=s.Point(s.sqrt(3)-1,0)
checks['F12_AB2']=str(A.distance(B)**2)
checks['F12_AC2']=str(s.simplify(A.distance(C)**2))
checks['F12_DF2']=str(s.simplify(A.distance(F)**2))
checks['F12_BC_minus_EF']=str(s.simplify(B.distance(C)-B.distance(F)))
assert all(checks[k]=='0' for k in ['F04_DA_dot_DE','F04_DA_norm2','F04_DE_norm2','C05_tangent_dot'])
assert checks['F11_noncyclic_det']!='0' and checks['C14_noncyclic_det']!='0'
assert checks['F12_AB2']=='4' and checks['F12_AC2']==checks['F12_DF2']=='2'
(D/'exact-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
