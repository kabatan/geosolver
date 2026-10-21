"""Coarse local sensitivity search; does not prove fabrication robustness."""
import json
import numpy as np
import rational_linkage as r

def perturbation_matrix(p):
    E=np.zeros((36,30));row=0;lengthcol=0
    for j in range(3):
        for _ in range(2):
            for L in (r.LONG,r.SHORT,r.SHORT):
                E[row,lengthcol]=L;row+=1;lengthcol+=1
    for j,u,v,alpha in [(0,'Q0','Q1',.5),(1,'D0','Q2',1/3)]:
        E[row,lengthcol]=r.ARM;row+=1;lengthcol+=1
        z=alpha*(p[f'B{j}']-p[u]);E[row:row+2,26+2*j]=[z.real,z.imag];row+=2
        E[row,lengthcol]=r.ARM;row+=1;lengthcol+=1
        z=alpha*(p[v]-p[f'B{j}']);E[row:row+2,27+2*j]=[z.real,z.imag];row+=2
        E[row,lengthcol]=alpha*r.ARM;row+=1;lengthcol+=1
        E[row,lengthcol]=(1-alpha)*r.ARM;row+=1;lengthcol+=1
    assert row==34 and lengthcol==26
    return E

def evaluate(samples):
    gain=0.;mins=1.;size=0.
    for w,z in samples:
        p=r.points(z);_,J=r.rows(p,w)
        C=np.linalg.solve(J.T,np.eye(36)[:,:2]).T @ perturbation_matrix(p)
        gain=max(gain,float(np.linalg.norm(C,ord=2)))
        mins=min(mins,float(np.linalg.svd(J,compute_uv=False)[-1]))
        vals=np.array(list(p.values()));size=max(size,float(np.ptp(vals.real)),float(np.ptp(vals.imag)))
    return {'sensitivity_2norm':gain,'min_sampled_sigma':mins,'span':size}

def main():
    samples=[]
    for b in r.CRIT_W[:2]:
        for w in r.loop(b,90)[::9]:
            for z in r.inverse_roots(w): samples.append((w,z))
    result=[]
    for K in [.01,.03,.05,.07,.085,4.02,4.2,4.5,5,6,8,12]:
        r.K=K
        mids=[];dist=[]
        for w,z in samples:
            v=z-r.POLES; mids.extend(abs((v+K/np.conj(v))/2))
            q=r.POLES+K/(np.conj(z)-r.POLES)
            dist.extend([abs(q[0]-q[1]),abs((q[0]+q[1])/2-q[2])])
        amin=max(mids);smin=max(dist)/2
        for a_scale in [1.025,1.15,1.5,2.]:
            r.LONG=amin*a_scale;r.SHORT=np.sqrt(r.LONG**2-K)
            for arm_scale in [1.025,1.15,1.5,2.]:
                r.ARM=smin*arm_scale
                metrics=evaluate(samples)
                result.append({'K':K,'long':r.LONG,'short':r.SHORT,'arm':r.ARM,**metrics})
        print(K,min(x['sensitivity_2norm'] for x in result if x['K']==K),flush=True)
    result.sort(key=lambda x:x['sensitivity_2norm'])
    (r.OUT/'component_optimization.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result[:8],indent=2))

if __name__=='__main__':main()
