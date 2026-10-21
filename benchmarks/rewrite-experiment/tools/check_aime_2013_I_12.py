# ruff: noqa
import sys,json,math,random,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from dsl_eval import *
from scipy.optimize import brentq
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','derivation','dsl')
A=json.load(open(f'{D}/AIME-2013-I-12.A.json'));R=json.load(open(f'{D}/AIME-2013-I-12.R.json'))
import numpy as np
s3=math.sqrt(3)
def cr(r,X):
  P=(r/(1+s3),s3*r/(1+s3)); return (r-P[0])*(X[1]-P[1])-(0-P[1])*(X[0]-P[0])
xa=[]
for X in [(2.5,s3/2),(2,s3)]:
  rs=np.linspace(0.5,20,800)
  for k in range(len(rs)-1):
    if cr(rs[k],X)*cr(rs[k+1],X)<0:
      r0=brentq(lambda r:cr(r,X),rs[k],rs[k+1],xtol=1e-15)
      rr,ok,_=resid(A,[r0]); print(' cand r',r0,ok,max(map(abs,rr)))
      if ok and max(map(abs,rr))<1e-9: xa.append([r0])
ta=sorted({round(target(A,x),9) for x in xa}); print('A',len(xa),ta,[round(x[0],6) for x in xa])
rng=random.Random(7); out=[]
for x in xa:
  e=env(A,x)
  zx=sum(float(e[n].x) for n in 'ABCDEF')/6; zy=sum(float(e[n].y) for n in 'ABCDEF')/6
  ux,uy=float(e['A'].x)-zx,float(e['A'].y)-zy
  bx,by=float(e['B'].x)-zx,float(e['B'].y)-zy
  sg=1 if ux*by-uy*bx>0 else -1
  base=[x[0],zx,zy,ux,uy,sg]
  r0,ok0,_=resid(R,base); print(' base R resid',max(map(abs,r0)),ok0,'target',target(R,base))
  for k in range(6):
    s=[v+rng.uniform(-.4,.4) for v in base]; s[5]=rng.choice([1,-1])*rng.uniform(.8,1.2)
    def F(w):
      try: return resid(R,w)[0]
      except Exception: return [1e3]*7
    sol=least_squares(F,s,xtol=1e-15,ftol=1e-15,gtol=1e-15,max_nfev=300)
    rr,ok,_=resid(R,sol.x)
    if ok and max(map(abs,rr))<1e-9: out.append(round(target(R,sol.x),9))
print('R feasible',len(out),sorted(set(out)))
