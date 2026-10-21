"""Check 2507 DA15 final formula, without returning a corrected proof to actor."""
import sympy as s,json
from pathlib import Path
p,q,b=s.symbols('p q b',real=True,nonzero=True)
S=p*p+q*q;k=(S-b*b)/(2*q)
A=s.Matrix([p,q]);B=s.Matrix([-b,0]);C=s.Matrix([b,0]);O=s.Matrix([0,k])
D=q*k/(S+p*b)*A;E=q*k/(S-p*b)*A
F=s.Matrix([p*(q*k+b*b)/S,q*q*k/S])
exprs={'D equidistant A B':(D-A).dot(D-A)-(D-B).dot(D-B),'E equidistant A C':(E-A).dot(E-A)-(E-C).dot(E-C),'F on BD':s.det(s.Matrix.hstack(F-B,D-B)),'F on CE':s.det(s.Matrix.hstack(F-C,E-C)),'AF perpendicular OF':(F-A).dot(F-O),'radius identity':(A-O).dot(A-O)-(B-O).dot(B-O)}
checks=[{'name':key,'remainder':str(s.factor(value)),'pass':s.factor(value)==0} for key,value in exprs.items()]
assert all(x['pass'] for x in checks)
Path(__file__).with_name('da15-candidate-checks.json').write_text(json.dumps(checks,indent=2)+'\n');print(len(checks),'checks passed')
