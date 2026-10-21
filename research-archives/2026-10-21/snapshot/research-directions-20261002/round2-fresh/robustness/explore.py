"""Search physical rational linkages. Independent of GeoSolver; sampled pilot only."""
import itertools,json,time,sys
from pathlib import Path
import numpy as np
OUT=Path(__file__).resolve().parent
PERMS=list(itertools.permutations(range(3)))
FIXED=[f'O{j}' for j in range(3)]
VARIABLES=['P']+sum(([f'Q{j}',f'A{j}',f'C{j}'] for j in range(3)),[])+sum(([f'B{j}',f'H{j}',f'E{j}',f'D{j}'] for j in range(2)),[])
N=len(VARIABLES);IX={v:i for i,v in enumerate(VARIABLES+FIXED)}
EDGES=[];LINES=[]
for j in range(3):
 for x in (f'A{j}',f'C{j}'):
  EDGES.extend([(f'O{j}',x,0),('P',x,1),(f'Q{j}',x,1)])
for j,u,v,a in [(0,'Q0','Q1',.5),(1,'D0','Q2',1/3)]:
 EDGES.extend([(u,f'B{j}',2),(f'B{j}',v,2),(f'H{j}',f'D{j}',(3,a)),(f'E{j}',f'D{j}',(3,1-a))])
 LINES.extend([(f'H{j}',u,f'B{j}',a),(f'E{j}',f'B{j}',v,a)])
IA=np.array([IX[a] for a,b,t in EDGES]);IB=np.array([IX[b] for a,b,t in EDGES]);ALPHA=np.array([a for d,u,v,a in LINES])

def loop(home,b,radius,n=180):
 start=b+radius*(home-b)/abs(home-b);a=np.angle(start-b);m=n//6
 return np.r_[np.linspace(home,start,m,endpoint=False),b+radius*np.exp(1j*np.linspace(a,a+2*np.pi,n-2*m,endpoint=False)),np.linspace(start,home,m+1)]

class Design:
 def __init__(self,poles,home,branches,radii):
  self.poles=np.array(poles,dtype=complex);self.poly=np.poly(self.poles);self.der=np.polyder(self.poly);self.home=home
  self.critical_z=np.roots(np.polysub(np.polymul(np.polyder(self.der),self.poly),np.polymul(self.der,self.der)))
  self.critical_w=np.conj(np.polyval(self.der,self.critical_z)/np.polyval(self.poly,self.critical_z))
  self.branches=branches;self.radii=radii
  self.homez=np.array(sorted(self.roots(home),key=lambda z:(z.real,z.imag)))
 def roots(self,w):return np.roots(np.polysub(np.conj(w)*self.poly,self.der))
 def track(self,n=180):
  self.paths=[];self.tracks=[];self.permutations=[]
  for j,r in zip(self.branches,self.radii):
   path=loop(self.home,self.critical_w[j],r,n);z=self.homez.copy();hist=[z.copy()]
   for w in path[1:]:
    roots=self.roots(w);p=min(PERMS,key=lambda p:np.sum(abs(roots[list(p)]-z)**2));z=roots[list(p)];hist.append(z.copy())
   self.paths.append(path);self.tracks.append(np.array(hist));self.permutations.append(np.argmin(abs(z[:,None]-self.homez),axis=1).tolist())
  p,q=np.array(self.permutations)
  self.noncommuting=not np.array_equal(p[q],q[p]);return self.noncommuting
 def choose(self,K,long_scale=1.3,arm_scale=1.3):
  self.K=K;z=np.concatenate(self.tracks).reshape(-1);v=z[:,None]-self.poles
  q=self.poles+K/np.conj(v);m=(v+K/np.conj(v))/2
  self.long=np.max(abs(m))*long_scale;self.short=np.sqrt(self.long**2-K)
  self.arm=np.max(np.stack([abs(q[:,0]-q[:,1]),abs((q[:,0]+q[:,1])/2-q[:,2])]))/2*arm_scale
  if not np.isfinite(self.short):raise ValueError('short')
  self.lengths=np.array([self.long if t==0 else self.short if t==1 else self.arm if t==2 else t[1]*self.arm for a,b,t in EDGES]);return self
 def points(self,z):
  z=np.atleast_1d(z);p=np.zeros((len(z),N+3),dtype=complex);p[:,0]=z;p[:,-3:]=self.poles
  for j,c in enumerate(self.poles):
   v=z-c;q=self.K/np.conj(v);mid=(v+q)/2;h=np.sqrt(self.long**2-abs(mid)**2);s=1j*v/abs(v)*h
   p[:,IX[f'Q{j}']]=c+q;p[:,IX[f'A{j}']]=c+mid+s;p[:,IX[f'C{j}']]=c+mid-s
  for j,u,v,a in [(0,'Q0','Q1',.5),(1,'D0','Q2',1/3)]:
   U,V=p[:,IX[u]],p[:,IX[v]];d=abs(V-U);B=(U+V)/2+1j*(V-U)/d*np.sqrt(self.arm**2-d*d/4);H=(1-a)*U+a*B;E=(1-a)*B+a*V;D=H+E-B
   for name,val in [(f'B{j}',B),(f'H{j}',H),(f'E{j}',E),(f'D{j}',D)]:p[:,IX[name]]=val
  return np.stack([p.real,p.imag],axis=-1)
 def rows(self,X,w,L=None,alpha=None,anchors=None):
  L=self.lengths if L is None else L;alpha=ALPHA if alpha is None else alpha;k=len(X)
  anchors=np.stack([self.poles.real,self.poles.imag],axis=-1) if anchors is None else anchors
  p=np.concatenate((X,np.broadcast_to(anchors,(k,3,2))),axis=1);d=p[:,IA]-p[:,IB]
  r=np.zeros((k,36));J=np.zeros((k,36,36));r[:,:26]=(np.sum(d*d,axis=2)-L*L)/(2*L)
  for i,(a,b,_) in enumerate(EDGES):
   for v,s in [(a,1),(b,-1)]:
    if IX[v]<N:J[:,i,2*IX[v]:2*IX[v]+2]+=s*d[:,i]/L[i]
  for i,(d,u,v,_) in enumerate(LINES):
   row=26+2*i;r[:,row:row+2]=p[:,IX[d]]-(1-alpha[i])*p[:,IX[u]]-alpha[i]*p[:,IX[v]]
   for nm,c in [(d,1),(u,-(1-alpha[i])),(v,-alpha[i])]:
    if IX[nm]<N:J[:,row,2*IX[nm]]=c;J[:,row+1,2*IX[nm]+1]=c
  target=np.mean(self.poles)+self.K*np.asarray(w)/3;r[:,-2:]=p[:,IX['D1']]-np.stack([np.real(target),np.imag(target)],axis=-1)
  J[:,-2,2*IX['D1']]=1;J[:,-1,2*IX['D1']+1]=1
  return r,J
 def evaluate(self,stride=10):
  z=np.concatenate([h[::stride].reshape(-1) for h in self.tracks]);w=np.concatenate([np.repeat(p[::stride],3) for p in self.paths]);p=self.points(z);r,J=self.rows(p[:,:N],w)
  E=np.zeros((len(z),36,30));E[:,:26,:26]=np.diag(self.lengths)
  for i,(d,u,v,a) in enumerate(LINES):E[:,26+2*i:28+2*i,26+i]=a*(p[:,IX[v]]-p[:,IX[u]])
  C=np.linalg.solve(J,E)[:,:2];sensitivity=np.max(np.linalg.svd(C,compute_uv=False)[:,0]);sigma=np.min(np.linalg.svd(J,compute_uv=False)[:,-1]);sep=min(np.min(abs(h[:,i]-h[:,j])) for h in self.tracks for i,j in itertools.combinations(range(3),2));span=np.max(np.ptp(p,axis=1))
  return {'sensitivity':float(sensitivity),'sigma_min':float(sigma),'separation':float(sep),'sensitivity_per_separation':float(sensitivity/sep),'span':float(span),'residual':float(np.max(abs(r))),'min_pole':float(np.min(abs(z[:,None]-self.poles))),'max_pole':float(np.max(abs(z[:,None]-self.poles)))}
 def serialize(self):return {'poles':[[z.real,z.imag] for z in self.poles],'home':[self.home.real,self.home.imag],'branches':self.branches,'radii':self.radii,'K':self.K,'long':self.long,'short':self.short,'arm':self.arm,'permutations':self.permutations,'homez':[[z.real,z.imag] for z in self.homez]}

def load(d,n=180):
 des=Design([complex(*z) for z in d['poles']],complex(*d['home']),d['branches'],d['radii']);des.track(n);des.K=d['K'];des.long=d['long'];des.short=d['short'];des.arm=d['arm'];des.lengths=np.array([des.long if t==0 else des.short if t==1 else des.arm if t==2 else t[1]*des.arm for a,b,t in EDGES]);return des

def main():
 start=time.monotonic();out=[]
 for geom in ['old','triangle']:
  poles=[-1,0,1] if geom=='old' else np.exp(2j*np.pi*np.arange(3)/3)
  if geom=='old':homes=[2.2j];branchpairs=[(1,0)];radii=[.32]
  else:homes=[.6+.3j,.9+.15j,1.3+.2j,1.9+.2j,2.2j];branchpairs=list(itertools.combinations(range(4),2));radii=[.35,.6,.9]
  for home,pair,radius in itertools.product(homes,branchpairs,radii):
   d=Design(poles,home,list(pair),[radius,radius]);okay=d.track()
   if not okay:continue
   for K in [-.03,-.1,-.3,-1,-3,-10,.03,.1,.3,1,3,10]:
    # positive K cannot cross P=Q radius anywhere on either lifted path
    r=abs(np.concatenate(d.tracks)[:,:,None]-d.poles)
    if K>0 and np.min(r)**2<K<np.max(r)**2:continue
    for ls,ars in [(1.15,1.15),(1.4,1.4),(2.,1.4)]:
     try:
      d.choose(K,ls,ars);metrics=d.evaluate(stride=15)
      if metrics['residual']>1e-8:continue
      out.append({**d.serialize(),**metrics,'geometry':geom})
     except (ValueError,np.linalg.LinAlgError):continue
   if len(out)%100<40:print(geom,home,pair,radius,len(out),'best',min((x['sensitivity_per_separation'] for x in out),default=None),'sec',time.monotonic()-start,flush=True)
  out.sort(key=lambda x:x['sensitivity_per_separation']);(OUT/'search.json').write_text(json.dumps(out,indent=2))
 print('TOP',json.dumps(out[:5],indent=2),flush=True)
if __name__=='__main__':main()
