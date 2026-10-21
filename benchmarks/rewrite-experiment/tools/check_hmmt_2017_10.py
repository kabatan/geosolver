# ruff: noqa
import sys,json,math,random,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from dsl_eval import *
from scipy.optimize import brentq
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','dsl'); i='HMMT-2017-FEB-GEO-10'
A=json.load(open(f'{D}/{i}.A.json'));B=json.load(open(f'{D}/{i}.B.json'));C=json.load(open(f'{D}/{i}.C.json'))
d=[12,16,14,11]
r=brentq(lambda r: sum(math.asin(r/x) for x in d)-math.pi,0.1,10.99)
# vertices A(12),B(16),C(14),D(11); T1 between A,B; T2 between B,C; T3 between C,D; T4 between D,A
th2=2*math.acos(r/16); th3=th2+2*math.acos(r/14); th4=th3+2*math.acos(r/11)
x0=[r,math.tan(th2/2),math.tan(th3/2),math.tan(th4/2)]
rng=random.Random(5); starts=[x0]+[[v*(1+rng.uniform(-.05,.05)) for v in x0] for _ in range(5)]
xs=[]
for s in starts:
  def F(x):
    try: return resid(A,x)[0]
    except Exception: return [1e3]*8
  sol=least_squares(F,s,xtol=1e-15,ftol=1e-15,gtol=1e-15)
  rr,ok,_=resid(A,sol.x)
  if ok and max(map(abs,rr))<1e-9: xs.append(list(sol.x))
newv=C['variables'][4:]; pts=['A','B','C','D','M','N']
fw=[];xcs=[]
for x in xs:
  e=env(A,x); ta=target(A,x)
  rb,okb,_=resid(B,x)
  xc=list(x)+[q for n in pts for q in (float(e[n].x),float(e[n].y))]; xcs.append(xc)
  rc,okc,_=resid(C,xc)
  fw.append((round(ta,9),okb and max(map(abs,rb))<1e-8, abs(target(B,x)-ta)<1e-9, okc and max(map(abs,rc))<1e-8, abs(target(C,xc)-ta)<1e-9))
print('forward',len(fw),fw[:3])
# backward: perturb all C vars by up to 20% and re-solve C
bw=[]
for k in range(30):
  s=[v*(1+rng.uniform(-.2,.2))+rng.uniform(-.5,.5) for v in xcs[k%len(xcs)]]
  def G(x):
    try: return resid(C,x)[0]
    except Exception: return [1e3]*20
  sol=least_squares(G,s,xtol=1e-15,ftol=1e-15,gtol=1e-15,max_nfev=5000)
  rc,okc,ec=resid(C,sol.x)
  if not(okc and max(map(abs,rc))<1e-9): continue
  ra,oka,ea=resid(A,sol.x[:4])
  dp=max(math.hypot(float(ea[n].x)-float(ec[n].x),float(ea[n].y)-float(ec[n].y)) for n in pts)
  bw.append((oka and max(map(abs,ra))<1e-8, dp<1e-7, abs(target(A,sol.x[:4])-target(C,sol.x))<1e-9, round(target(C,sol.x),9)))
print('backward',len(bw),sorted(set(bw)))
