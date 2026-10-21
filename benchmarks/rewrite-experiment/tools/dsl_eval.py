# ruff: noqa
"""Numerical evaluator for GeoSolver DSL files, used only to check that rewritten DSLs are equivalent (not the solver)."""
import json,sys,math,random,warnings
warnings.filterwarnings('ignore')
import geosolver.geometry as g
import numpy as np
from scipy.optimize import least_squares
NS={n:getattr(g,n) for n in dir(g) if not n.startswith('_')}
NS.update(pi=math.pi,abs=abs,min=min,max=max)
def _cvx(pts):
  n=len(pts); s=[]
  for k in range(n):
    a,b,c=pts[k],pts[(k+1)%n],pts[(k+2)%n]
    s.append(float((b.x-a.x)*(c.y-b.y)-(b.y-a.y)*(c.x-b.x)))
  return all(v>1e-9 for v in s) or all(v<-1e-9 for v in s)
NS['ConvexPolygon']=_cvx
NS['Or']=lambda *a: any(bool(x) for x in a)
NS['And']=lambda *a: all(bool(x) for x in a)
NS['Not']=lambda a: not bool(a)

def env(d,vals):
  e=dict(NS); e.update(dict(zip(d['variables'],vals)))
  for c in d['constructions']:
    e[c['name']]=eval(c['expression'],e)
  return e
def num(x):
  return float(x)
def resid(d,vals):
  e=env(d,vals); r=[];ok=True
  for c in d['conditions']:
    if 'predicate' in c:
      try: v=eval(c['predicate'],e); ok=ok and bool(v)
      except Exception: ok=False
      continue
    L=num(eval(str(c['left']),e)); R=num(eval(str(c['right']),e))
    op=c['operator']
    if op=='=': r.append(L-R)
    elif op=='>': ok=ok and L>R+1e-7
    elif op=='>=': ok=ok and L>=R-1e-12
    elif op=='<': ok=ok and L<R-1e-7
    elif op=='<=': ok=ok and L<=R+1e-12
    elif op=='!=': ok=ok and abs(L-R)>1e-9
  return r,ok,e
def target(d,vals):
  return num(eval(d['target'],env(d,vals)))
def find(d,tries=400,seed=0,scale=10):
  rng=random.Random(seed); n=len(d['variables']); out=[]
  for _ in range(tries):
    x0=[rng.uniform(-scale,scale) for _ in range(n)]
    def F(x):
      try:
        r,_,_=resid(d,x); return r if r else [0.0]
      except Exception: return [1e3]*max(1,sum(1 for c in d['conditions'] if c.get('operator')=='='))
    try:
      s=least_squares(F,x0,xtol=1e-15,ftol=1e-15,gtol=1e-15,max_nfev=3000)
      r,ok,_=resid(d,s.x)
      if ok and max([abs(v) for v in r]+[0])<1e-9: out.append(list(s.x))
    except Exception: pass
    if len(out)>=8: break
  return out
