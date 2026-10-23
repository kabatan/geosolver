"""Exploratory fresh-sample confirmation, separate from preregistered outcomes."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from experiment import OUT, IDS, EPS, VERIFY_EPS, check_lock, build, local, save, utc
import numpy as np

CASES=['AIME-2023-I-05','AIME-2025-I-02']

def run(cid,block):
    check_lock()
    inp=next(i for i in json.loads((OUT/'inputs.json').read_text()) if i['id']==cid)
    patches=json.loads((OUT/f'patches/{cid}.json').read_text())['patches']
    b,ev=build(inp)
    width=np.diff(np.asarray(inp['box']),axis=1).ravel(); low=np.asarray(inp['box'])[:,0]
    rep=block//8; patch=(block%8)//4; offset=(block%4)*64
    rng=np.random.default_rng(np.random.SeedSequence([340601+rep,IDS.index(cid),patch]))
    ys=np.asarray(patches[patch]['center'])+rng.uniform(-.005,.005,(256,len(width)))
    vs=rng.normal(size=ys.shape);vs/=np.linalg.norm(vs,axis=1)[:,None]
    rows=[];verified=[]
    for j in range(offset,offset+64):
        x=low+ys[j]*width;v=vs[j]
        s={'i':rep*512+patch*256+j,'rep':rep,'patch':patch,'j':j,'start':x,'v':v}
        row={**s,'base':local(inp,b,ev,x),'variants':[]}
        for e in EPS:
            y=x+e*width*v
            row['variants'].append({'eps':e,'actual_eps':float(np.linalg.norm((y-x)/width)),
                'same_bits':bool(np.array_equal(x,y)),'r':local(inp,b,ev,y)})
        y=x.copy();coord=s['i']%len(x);y[coord]=np.nextafter(y[coord],np.inf)
        row['ulp']={'coord':coord,'actual_eps':float(np.linalg.norm((y-x)/width)),'r':local(inp,b,ev,y)}
        if j<4:row['repeat']=local(inp,b,ev,x)
        if j<8:
            q={**s,'base':local(inp,b,ev,x,320),'variants':[]}
            for e in VERIFY_EPS:
                q['variants'].append({'eps':e,'r':local(inp,b,ev,x+e*width*v,320)})
            verified.append(q)
        rows.append(row)
    save(f'dense/{cid}-{block:02d}.json',{'utc':utc(),'id':cid,'rows':rows,'verified':verified})

def batch():
    check_lock(); start=time.monotonic();active=[];pending=[]
    for cid in CASES:
        for block in range(16):
            if not (OUT/f'dense/{cid}-{block:02d}.json').exists():pending.append((cid,block))
    while pending or active:
        while pending and len(active)<3 and time.monotonic()-start<75:
            cid,block=pending.pop(0)
            f=(OUT/'logs'/f'dense-{cid}-{block}.log').open('w')
            p=subprocess.Popen([sys.executable,'-B',str(Path(__file__)),cid,str(block)],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            active.append((p,time.monotonic(),f,cid,block))
        rest=[]
        for p,t,f,cid,block in active:
            rc=p.poll()
            if rc is None and time.monotonic()-t>90:
                os.killpg(p.pid,signal.SIGKILL);p.wait();rc=p.returncode
            if rc is None:rest.append((p,t,f,cid,block))
            else:
                f.close();print(cid,block,rc,round(time.monotonic()-t,2),flush=True)
        active=rest
        if not active and (not pending or time.monotonic()-start>=75):break
        time.sleep(.2)
    print('remaining',len(pending),'sec',round(time.monotonic()-start,2),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='batch':batch()
    else:run(sys.argv[1],int(sys.argv[2]))
