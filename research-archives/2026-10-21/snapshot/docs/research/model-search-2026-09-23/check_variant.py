import sympy as s,json
from pathlib import Path
p=2*s.sqrt(3)/5;q=s.Rational(11,10);S=p*p+q*q
A=s.Matrix([p,q]);B=s.Matrix([-1,0]);C=s.Matrix([1,0]);O=s.Matrix([0,(S-1)/(2*q)])
F=s.Matrix([p*(S+1)/(2*S),q*(S-1)/(2*S)])
R2=s.simplify((A-O).dot(A-O));AF2=s.simplify((A-F).dot(A-F));OF2=s.simplify((O-F).dot(O-F));scale2=169/R2
wA=s.simplify(F[1]/q);wC=s.simplify((F[0]-p*wA+1-wA)/2);wB=1-wA-wC
checks={'acute_A':S>1,'acute_B':p>-1,'acute_C':p<1,'scalene':p!=0,'F_inside':all(bool(w>0) for w in [wA,wB,wC]),'AO2':s.simplify(R2*scale2)==169,'AF2':s.simplify(AF2*scale2)==121,'OF2':s.simplify(OF2*scale2)==48}
assert all(checks.values())
Path(__file__).with_name('variant-check.json').write_text(json.dumps({'normalized_A':[str(p),str(q)],'scale_squared':str(scale2),'checks':{k:bool(v) for k,v in checks.items()}},indent=2)+'\n')
print(checks)
