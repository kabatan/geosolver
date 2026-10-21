"""CPU checks of equations cited in reviews; not supplying proofs to Qwen."""
import json
from pathlib import Path
import sympy as s
HERE=Path(__file__).resolve().parent
checks=[]
def eq(name, expression):
    remainder=s.factor(expression)
    checks.append({'name':name,'remainder':str(remainder),'pass':remainder==0})
    assert remainder==0,(name,remainder)
x,y,m=s.symbols('x y m',real=True,nonzero=True)
A=s.Matrix([x,y]);H=s.Matrix([x,(m*m-x*x)/y]);P=m*m/(x*x+y*y)*A
# H01 written general projection equations.
eq('H01:H lies on B altitude',s.Matrix([x+m,H[1]]).dot(s.Matrix([x-m,y])))
eq('H01:P projection',(H-P).dot(A))
eq('H01:r=10,m=6 gives P=9A/25',s.Rational(6**2,10**2)-s.Rational(9,25))
# H02 expected centers, checked directly against all three explicitly constructed circle points.
a=s.Matrix([6,8]);cases=[(s.Matrix([s.Rational(56,17),s.Rational(320,17)]),s.Matrix([-s.Rational(184,65),s.Rational(192,65)]),s.Matrix([-2,s.Rational(47,4)])),(s.Matrix([s.Rational(80,17),s.Rational(224,17)]),s.Matrix([-s.Rational(16,65),s.Rational(288,65)]),s.Matrix([1,s.Rational(19,2)]))]
for i,(u,v,z) in enumerate(cases):
    eq(f'H02 circle{i+1} AU',(a-z).dot(a-z)-(u-z).dot(u-z))
    eq(f'H02 circle{i+1} AV',(a-z).dot(a-z)-(v-z).dot(v-z))
d=cases[0][2]-cases[1][2]
eq('H02:center separation',d.dot(d)-s.Rational(15,4)**2)
# H04: the excluded D=9 branch has A=P and a right angle at A.
a,b=s.symbols('a b',real=True,nonzero=True)
D=(a-3)**2+b*b;A=s.Matrix([a,b]);P=s.Matrix([3+9*(a-3)/D,9*b/D]);T=s.Matrix([-2,0])
TA2=(A-T).dot(A-T);TP2=(P-T).dot(P-T)
eq('H04:equal-distance factorization',TA2-TP2-(D-9)*(TA2-16)/D)
eq('H04:acute nondegenerate witness AT4',TA2.subs({a:1,b:s.sqrt(7)})-16)
# DA01 submitted centers and intersection in A=(0,0), C=(9,0) coordinates.
b=s.Matrix([s.Rational(11,3),8*s.sqrt(5)/3]);c=s.Matrix([9,0])
o1=s.Matrix([0,147*s.sqrt(5)/80]);o2=s.Matrix([s.Rational(9,2),-99*s.sqrt(5)/80])
t=s.Matrix([s.Rational(369,98),54*s.sqrt(5)/49])
eq('DA01:first center equidistant A B',(b-o1).dot(b-o1)-o1.dot(o1))
eq('DA01:second center equidistant A C',(c-o2).dot(c-o2)-o2.dot(o2))
eq('DA01:second center tangent to AB',o2.dot(b))
eq('DA01:T on first circle',(t-o1).dot(t-o1)-o1.dot(o1))
eq('DA01:T on second circle',(t-o2).dot(t-o2)-o2.dot(o2))
eq('DA01:AT',t.dot(t)-s.Rational(9,2)**2)
bad_o=s.Matrix([0,1323*s.sqrt(5)/80]);c_alt=s.Matrix([s.Rational(33,7),24*s.sqrt(5)/7])
res=s.simplify((c_alt-bad_o).dot(c_alt-bad_o)-bad_o.dot(bad_o))
checks.append({'name':'DA01 X061 alleged circle does not pass C','remainder':str(res),'pass':res!=0})
assert res!=0
# DA03 audit of the underlying unique answer using general algebra (not fed to Qwen).
u,v,c=s.symbols('u v c',real=True,nonzero=True)
sq=u*u+v*v;den=sq+c*c+2*c*u
B=s.Matrix([c,0]);C=s.Matrix([u,v]);O=s.Matrix([c/2,(sq-c*u)/(2*v)])
T=s.Matrix([c*(sq+c*u)/den,c*c*v/den])
K=s.Matrix([c*(sq-c*u)/(sq-c*c),-c*c*v/(sq-c*c)])
eq('DA03:T in circle AC tangent AB',T.dot(T)-sq*T[1]/v)
mat=s.Matrix([[p.dot(p),p[0],p[1],1] for p in [B,O,C,T]])
eq('DA03:T in circle BOC',mat.det())
eq('DA03:K B C collinear',s.det(s.Matrix.hstack(K-B,C-B)))
eq('DA03:K O T collinear',s.det(s.Matrix.hstack(K-O,T-O)))
eq('DA03:AK perpendicular AO',K.dot(O))
eq('DA03:AK squared equals external secant product',K.dot(K)-c*c*sq*((u-c)**2+v*v)/(sq-c*c)**2)
eq('DA03:label sqrt(49*81)=63',s.sqrt(49*81)-63)
# DA04: submitted coordinate formulae; no repair is supplied to the policy.
k=s.symbols('k',real=True,nonzero=True)
A=s.Matrix([0,0]);B=s.Matrix([11,0]);P=s.Matrix([3,0])
O=s.Matrix([s.Rational(11,2),k]);O1=s.Matrix([s.Rational(3,2),3*k/11]);O2=s.Matrix([7,8*k/11])
direction=s.Matrix([10*k,-121]);tau=-96*k/(100*k*k+14641);Q=P+tau*direction
eq('DA04:Q on first circle',(Q-O1).dot(Q-O1)-O1.dot(O1))
eq('DA04:Q on second circle',(Q-O2).dot(Q-O2)-(B-O2).dot(B-O2))
eq('DA04:PQ formula',(Q-P).dot(Q-P)-9216*k*k/(100*k*k+14641))
eq('DA04:Q is foot of O to PQ',(O-Q).dot(direction))
d2=(121*O[0]+10*k*O[1]-363)**2/(121**2+100*k*k)
k2=s.Rational(366025,6716)
eq('DA04:XY14 at submitted k2',(O.dot(O)-d2-49).subs(k*k,k2))
eq('DA04:correct PQ label',(9216*k*k/(100*k*k+14641)-25).subs(k*k,k2))
wrong=s.factor((9216*k*k/(100*k*k+14641)-25).subs(k*k,s.Rational(109,2)))
checks.append({'name':'DA04 X051 k2=109/2 does not yield exactly PQ=5','remainder':str(wrong),'pass':wrong!=0})
assert wrong!=0
# DA05 / DA15: generic identities for auditing candidate arguments, not training inputs.
u,v,c=s.symbols('u v c',real=True,nonzero=True)
sq=u*u+v*v;den=sq+c*c+2*c*u
A=s.Matrix([u,v]);B=s.zeros(2,1);C=s.Matrix([c,0]);M=C/2
D=s.Matrix([c*(sq+c*u)/den,c*c*v/den]);t=s.symbols('t')
parameter=s.solve(s.det(s.Matrix.hstack(M+t*(D-M)-C,A-C)),t)[0]
E=s.simplify(M+parameter*(D-M))
eq('DA05:MD ME product for M D E order',s.simplify(parameter*(D-M).dot(D-M))-c*c/4)
eq('DA05:E lies on first circle',E.dot(E)-sq*E[1]/v)
eq('DA05:DE label',s.Rational(12**2,4)/4-4-5)
A=s.zeros(2,1);B=s.Matrix([c,0]);C=s.Matrix([u,v]);M=(B+C)/2
O=s.Matrix([c/2,(sq-c*u)/(2*v)])
D=c/(2*(c+u))*(B+C);E=sq/(2*(sq+c*u))*(B+C)
t1,t2=s.symbols('t1 t2')
par=s.solve(B+t1*(D-B)-C-t2*(E-C),(t1,t2))
F=s.simplify(B+par[t1]*(D-B))
eq('DA15:F in diameter AO circle',F.dot(O-F))
eq('DA15:OF label',s.sqrt(13**2-12**2)-5)
(HERE/'algebra-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'checks':len(checks),'passed':sum(r['pass'] for r in checks)}))
