# ruff: noqa
import sys, json, copy, mpmath
sys.argv=['x']; sys.path.insert(0,'benchmarks/new-2026/verify')
import check_dsl as c
dsl=json.load(open('benchmarks/new-2026/dsl/HMMT-2026-FEB-GEO-09.json'))
_,_,b,ev=c.load_dict(dsl)
x0=[6.31662479036,1.25856365305,4.83900997429,3.05806113731,-1.50147254977,3.33753742452]
xp,n=c.polish(ev,x0); print('norm',mpmath.nstr(n,3))
mpmath.mp.dps=60
for p in ['Distance(Center(K), Center(omega))','Radius(K)','Radius(omega)','Distance(E,F)','Radius(Gamma)','ay','a','rho','Distance(Point(zx,zy), Line(A,B))','Distance(Point(zx,zy), Line(A,C))']:
    d=copy.deepcopy(dsl); d['target']=p; d['id']='probe'
    _,_,b2,ev2=c.load_dict(d); print(mpmath.nstr(c.hp_target(ev2,xp),12),'|',p)
print(ev.evaluate_float_hard_feasibility([float(v) for v in xp]))
