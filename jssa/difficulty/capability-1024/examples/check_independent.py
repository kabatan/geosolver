"""Small independent checks of the original conditions; not solver scoring."""
import json,pathlib
from mpmath import mp
import sympy as s
O=pathlib.Path(__file__).resolve().parent
x,y,u,v,T=s.symbols('x y u v T')
eq=[2*x+u,2*y+v,2*x*x+2*y*y+u*u+v*v-250]
h2=(u-x)**2+(v-y)**2
G=s.groebner(eq+[T-h2],u,v,x,y,T,order='lex')
elim=[str(p.as_expr()) for p in G.polys if p.as_expr().free_symbols<={T}]
J=s.Matrix(eq).jacobian([x,y,u,v]);point={x:-5,y:-s.sqrt(s.Rational(50,3)),u:10,v:2*s.sqrt(s.Rational(50,3))}
checks={'AIME-2012-I-14':{'eliminated_target':elim,'jacobian_rank_at_nondegenerate_point':J.subs(point).rank(),'variables':4,'point':{str(k):str(w) for k,w in point.items()},'h_squared':str(h2.subs(point))}}
z=s.Integer(2014);w1=z*(-1+s.sqrt(3)*s.I)/2;w2=s.conjugate(w1)
area=3*s.sqrt(3)*z*z/4;n=3*z*z/4
checks['AIME-2014-II-10']={'w1':str(w1),'w2':str(w2),'reciprocal_equation_residual':str(s.simplify(1/(z+w1)-1/z-1/w1)),'area':str(area),'area_minpoly':str(s.minpoly(area,T)),'integer_n':str(n),'official_remainder':int(n)%1000}
with mp.workdps(110):
 p=[mp.mpc(mp.cos(2*mp.pi*k/5),mp.sin(2*mp.pi*k/5)) for k in range(5)]
 A,B,C,D,E=p;k=mp.mpc(mp.mpf('0.5'),-mp.sqrt(3)/2);F=A+k*(B-A);G=B+k*(C-B)
 dot=lambda a,b:mp.re(a*mp.conj(b))
 det=lambda a,b:mp.im(mp.conj(a)*b)
 angle=mp.atan2(abs(det(F-E,G-E)),dot(F-E,G-E))
 lengths=[abs(F-A),abs(F-B),abs(B-A),abs(G-B),abs(G-C),abs(C-B)]
 checks['HMMT-2024-FEB-GUTS-04']={'method':'independent complex coordinates; dot and determinant, 110 dps','degrees':mp.nstr(angle*180/mp.pi,100),'error_from_4pi_over_15':mp.nstr(abs(angle-4*mp.pi/15),8),'equilateral_edge_error':mp.nstr(max(lengths)-min(lengths),8),'external_orientation_cross_ABF':mp.nstr(det(B-A,F-A),20),'external_orientation_cross_BCG':mp.nstr(det(C-B,G-B),20)}
 # Check the spurious 50-dps polynomial proposal independently by root distance.
 a,b,c=1916119,-9942479000000,-810635500000000000
 wrong=(-mp.mpf(b)+mp.sqrt(mp.mpf(b)**2-4*a*c))/(2*a)
 checks['low_precision_proposal']={'distance_from_true_area':mp.nstr(abs(wrong-mp.mpf(3042147)*mp.sqrt(3)),15),'final_root_distance_tolerance_at_50_dps':'1e-30 * max(1,abs(area))'}
# Symbolic witnesses for the positive-dimensional extraneous components.
r=s.symbols('r',positive=True);RR=30-r
P0=s.Matrix([RR,0]);Q=s.Matrix([RR-2*r*r/RR,2*r*s.sqrt(RR*RR-r*r)/RR])
points=[P0,Q,P0,Q,P0,Q]
res=[s.simplify((p.dot(p))-RR**2) for p in points]
res += [s.simplify((points[j]-points[(j+1)%6]).dot(points[j]-points[(j+1)%6])-4*r*r) for j in range(6)]
assert all(t==0 for t in res)
checks['AIME-2005-I-01-degenerate-family']={'parameter':'0<r<15','all_12_squared_distance_residuals_zero':True,'repeated_centers':'P0=P2=P4; P1=P3=P5'}
p,q=s.symbols('p q');P=s.Matrix([p,q]);direction=s.Matrix([1,s.I])
Qbc=P-q/s.I*direction;Qca=P+(12-3*p-4*q)/(3+4*s.I)*direction;Qab=P-p*direction
res=[Qbc[1],3*Qca[0]+4*Qca[1]-12,Qab[0]]
res += [(P-a).dot(P-a) for a in [Qbc,Qca,Qab]]
assert all(s.simplify(t)==0 for t in res)
checks['HMMT-2019-FEB-GUTS-17-degenerate-family']={'parameters':['p','q'],'common_side_length':0,'all_side_incidence_and_squared_distance_residuals_zero':True,'isotropic_direction':['1','i']}
(O/'evidence/independent.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n');print(json.dumps(checks,ensure_ascii=False,indent=2))
