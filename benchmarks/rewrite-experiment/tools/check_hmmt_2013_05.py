# ruff: noqa
import sys,json,math,random,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from dsl_eval import *
from scipy.optimize import brentq
import numpy as np
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','dsl'); i='HMMT-2013-FEB-GEO-05'
A=json.load(open(f'{D}/{i}.A.json'));B=json.load(open(f'{D}/{i}.B.json'));C=json.load(open(f'{D}/{i}.C.json'))
def g(phi):
  ax,ay=math.sqrt(2)*math.cos(phi),1+math.sqrt(2)*math.sin(phi)
  # D second intersection of line A-M(0,0) with circle x^2+(y-1)^2=2
  # param t: X=t*(ax,ay); |X-(0,1)|^2=2 -> t^2|A|^2 -2t ay +1-2=0 ; roots t=1 and t=-1/|A|^2
  t=-1/(ax*ax+ay*ay); dx,dy=t*ax,t*ay
  return math.hypot(ax,ay)-2*math.hypot(dx,dy)
xa=[]
for sc in [1.0,2.5]:
  for sgn in [1,-1]:
    xs=[sc,sgn*sc*math.sqrt(7)/2,sc/2]; r,ok,_=resid(A,xs)
    if ok and max(map(abs,r))<1e-9: xa.append(xs)
print('A configs',len(xa))
pts=['K','D','O']; fw=[]; xcs=[]
for x in xa:
  e=env(A,x); e['K']=g_center=None
  import geosolver.geometry as G
  e['K']=G.Center(e['Gamma']); ta=target(A,x)
  rb,okb,_=resid(B,x)
  xc=list(x)+[q for n in pts for q in (float(e[n].x),float(e[n].y))]; xcs.append(xc)
  rc,okc,_=resid(C,xc)
  fw.append((round(ta,9),okb and max(map(abs,rb))<1e-8,abs(target(B,x)-ta)<1e-9,okc and max(map(abs,rc))<1e-8,abs(target(C,xc)-ta)<1e-9))
print('forward',fw)
rng=random.Random(9); bw=[]
for k in range(30):
  s=[v*(1+rng.uniform(-.25,.25))+rng.uniform(-.3,.3) for v in xcs[k%len(xcs)]]
  def F(w):
    try: return resid(C,w)[0]
    except Exception: return [1e3]*8
  sol=least_squares(F,s,xtol=1e-15,ftol=1e-15,gtol=1e-15,max_nfev=3000)
  rc,okc,ec=resid(C,sol.x)
  if not(okc and max(map(abs,rc))<1e-9): continue
  ra,oka,ea=resid(A,sol.x[:3]); ea['K']=G.Center(ea['Gamma'])
  dp=max(math.hypot(float(ea[n].x)-float(ec[n].x),float(ea[n].y)-float(ec[n].y)) for n in pts)
  bw.append((oka and max(map(abs,ra))<1e-8, dp<1e-7, abs(target(A,sol.x[:3])-target(C,sol.x))<1e-9, round(target(C,sol.x),9)))
print('backward',len(bw),sorted(set(bw)))
