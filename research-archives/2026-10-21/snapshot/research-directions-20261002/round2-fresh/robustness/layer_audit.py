"""Necessary static layer constraints for straight rods and vertical through-pins.
Near projected contacts are sampled. A feasible order is NOT a collision certificate.
"""
import json,itertools,time,sys
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix
from explore import OUT
from clearance_audit import RODS
threshold=float(sys.argv[1]) if len(sys.argv)>1 else .01
source='clearance_audit.json' if threshold==.01 else f'clearance_{threshold:.3f}.json'
near=json.loads((OUT/source).read_text());out=[]
for case in near:
 pairs=list(itertools.combinations(range(26),2));conf=case['near_pairs'];n=26+len(pairs)+len(conf);rows=[];low=[];high=[];M=27
 def append(d,lo=-np.inf,hi=np.inf):rows.append(d);low.append(lo);high.append(hi)
 for k,(i,j) in enumerate(pairs):
  b=26+k;append({i:1,j:-1,b:M},lo=1);append({i:-1,j:1,b:-M},lo=1-M)
 for k,c in enumerate(conf):
  i=c['rod_index'];b=26+len(pairs)+k
  incident=[h for h,rod in enumerate(RODS) if c['joint'] in rod]
  for h in incident:
   append({i:1,h:-1,b:M},lo=1);append({i:-1,h:1,b:-M},lo=1-M)
 A=lil_matrix((len(rows),n))
 for i,row in enumerate(rows):
  for j,v in row.items():A[i,j]=v
 start=time.monotonic();r=milp(np.zeros(n),integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.r_[np.full(26,25),np.ones(n-26)]),constraints=LinearConstraint(A.tocsr(),low,high),options={'time_limit':10,'mip_rel_gap':0})
 row={'name':case['name'],'status':int(r.status),'message':r.message,'seconds':time.monotonic()-start,'constraints':len(rows),'variables':n,'rod_layer_order':None if r.x is None else np.round(r.x[:26]).astype(int).tolist()};out.append(row);print(row,flush=True)
(OUT/('layer_audit.json' if threshold==.01 else f'layers_{threshold:.3f}.json')).write_text(json.dumps(out,indent=2))
