"""Projected clearance audit only. Not 3-D collision certification or CAD."""
import json,sys
import numpy as np
from explore import load,OUT,IX
from verify import old
RODS=[]
for j in range(3):
 for x in [f'A{j}',f'C{j}']:RODS.extend([[f'O{j}',x],['P',x],[f'Q{j}',x]])
for j,u,v in [(0,'Q0','Q1'),(1,'D0','Q2')]:RODS.extend([[u,f'H{j}',f'B{j}'],[f'B{j}',f'E{j}',v],[f'H{j}',f'D{j}'],[f'E{j}',f'D{j}']])
def audit(threshold=.01):
 res=[]
 for name,d in [('real_negative',old()),('triangle_refined',load(json.loads((OUT/'refinement_validation.json').read_text())['results'][5]['design']))]:
  d.track(900);pts=d.points(np.concatenate(d.tracks).reshape(-1));near=[];minimum=np.inf
  for i,rod in enumerate(RODS):
   a,b=pts[:,IX[rod[0]]],pts[:,IX[rod[-1]]];ab=b-a;l2=np.sum(ab*ab,axis=-1)
   for joint,j in IX.items():
    if joint in rod:continue
    ap=pts[:,j]-a;t=np.sum(ap*ab,axis=-1)/l2;dist=np.linalg.norm(ap-np.clip(t,0,1)[:,None]*ab,axis=-1);mn=float(np.min(dist));minimum=min(minimum,mn)
    if mn<threshold:near.append({'rod_index':i,'rod':rod,'joint':joint,'min_sampled_distance':mn})
  workspace=np.ptp(pts.reshape(-1,2),axis=0).tolist();res.append({'name':name,'configs':len(pts),'threshold':threshold,'projected_near_pairs':len(near),'minimum_projected_clearance':minimum,'full_swept_bbox':workspace,'near_pairs':near})
 return res
if __name__=='__main__':
 threshold=float(sys.argv[1]) if len(sys.argv)>1 else .01;res=audit(threshold);path='clearance_audit.json' if threshold==.01 else f'clearance_{threshold:.3f}.json';(OUT/path).write_text(json.dumps(res,indent=2));print(json.dumps([{k:v for k,v in x.items() if k!='near_pairs'} for x in res],indent=2))
