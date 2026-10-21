"""Independent inversion cell and pantograph dimensions, same rational map."""
import json,itertools,time
import numpy as np
from explore import Design,OUT,IX,N,ALPHA,EDGES
from verify import old,run
class Asymmetric(Design):
 def choose(self,K,outer=1.3,central=1.3,arm0=1.3,arm1=1.3):
  self.K=K;z=np.concatenate(self.tracks).reshape(-1);v=z[:,None]-self.poles;q=self.poles+K/np.conj(v);mid=(v+K/np.conj(v))/2
  self.long=np.max(abs(mid),axis=0)*[outer,central,outer];self.short=np.sqrt(self.long**2-K)
  self.arm=np.array([np.max(abs(q[:,0]-q[:,1])),np.max(abs((q[:,0]+q[:,1])/2-q[:,2]))])/2*[arm0,arm1]
  self.lengths=np.r_[np.array([[self.long[j],self.short[j],self.short[j]]*2 for j in range(3)]).reshape(-1),[self.arm[0],self.arm[0],self.arm[0]/2,self.arm[0]/2,self.arm[1],self.arm[1],self.arm[1]/3,2*self.arm[1]/3]];return self
 def points(self,z):
  z=np.atleast_1d(z);p=np.zeros((len(z),N+3),dtype=complex);p[:,0]=z;p[:,-3:]=self.poles
  for j,c in enumerate(self.poles):
   v=z-c;q=self.K/np.conj(v);mid=(v+q)/2;h=np.sqrt(self.long[j]**2-abs(mid)**2);s=1j*v/abs(v)*h
   p[:,IX[f'Q{j}']]=c+q;p[:,IX[f'A{j}']]=c+mid+s;p[:,IX[f'C{j}']]=c+mid-s
  for j,u,v,a in [(0,'Q0','Q1',.5),(1,'D0','Q2',1/3)]:
   U,V=p[:,IX[u]],p[:,IX[v]];d=abs(V-U);B=(U+V)/2+1j*(V-U)/d*np.sqrt(self.arm[j]**2-d*d/4);H=(1-a)*U+a*B;E=(1-a)*B+a*V;D=H+E-B
   for name,val in [(f'B{j}',B),(f'H{j}',H),(f'E{j}',E),(f'D{j}',D)]:p[:,IX[name]]=val
  return np.stack([p.real,p.imag],axis=-1)
 def serialize(self):
  a=super().serialize();a.update({'long':self.long.tolist(),'short':self.short.tolist(),'arm':self.arm.tolist()});return a

def main():
 o=old();d=Asymmetric(o.poles,o.home,o.branches,o.radii);d.track(360);out=[];start=time.monotonic()
 for K,outer,central,a0,a1 in itertools.product(-np.geomspace(.25,1.2,10),[1.08,1.3,1.7],[1.08,1.3,1.7],[1.08,1.3,1.7],[1.08,1.3,1.7]):
  d.choose(float(K),outer,central,a0,a1);r=d.evaluate(stride=18);out.append({**d.serialize(),**r,'scales':[outer,central,a0,a1]})
 out.sort(key=lambda x:x['sensitivity_per_separation']);(OUT/'asymmetric_search.json').write_text(json.dumps(out,indent=2));print('best',out[0],'seconds',time.monotonic()-start,flush=True)
 x=out[0];d.choose(x['K'],*x['scales']);res={'design':x,'base':run(d,d.lengths,ALPHA),'seed':202610026,'trials':[]};rng=np.random.default_rng(202610026)
 for level in [.01,.02,.03]:
  for trial in range(12):
   L=d.lengths*(1+rng.uniform(-level,level,26));alpha=ALPHA*(1+rng.uniform(-level,level,4));r=run(d,L,alpha);res['trials'].append({'level':level,'trial':trial,**r})
  print('level',level,'pass',sum(t['success'] for t in res['trials'] if t['level']==level),flush=True);(OUT/'asymmetric_validation.json').write_text(json.dumps(res,indent=2))
if __name__=='__main__':main()
