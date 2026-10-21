# ruff: noqa
import sys,json,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from dsl_eval import *
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','derivation','dsl')
i=sys.argv[1]; scale=float(sys.argv[2]) if len(sys.argv)>2 else 10
A=json.load(open(f'{D}/{i}.A.json'));R=json.load(open(f'{D}/{i}.R.json'))
if A['variables']:
  ta=sorted({round(target(A,x),9) for x in find(A,tries=200,seed=3)})
else:
  r,ok,_=resid(A,[]); ta=[round(target(A,[]),9)]; print(' A residual',max(map(abs,r)) if r else 0, ok)
xs=find(R,tries=600,seed=4,scale=scale)
tr=sorted({round(target(R,x),9) for x in xs})
print(i,'A targets',ta,'| R feasible',len(xs),'targets',tr, '| match' if tr and set(tr)==set(ta) else '| DIFF')
