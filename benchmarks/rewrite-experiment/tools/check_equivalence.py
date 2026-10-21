# ruff: noqa
import sys,json,math,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from dsl_eval import *
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','dsl')
ids=sys.argv[1:]
rep={}
for i in ids:
  A=json.load(open(f'{D}/{i}.A.json'));B=json.load(open(f'{D}/{i}.B.json'));C=json.load(open(f'{D}/{i}.C.json'))
  newv=C['variables'][len(A['variables']):]
  pts=sorted({v[1:] for v in newv},key=lambda n:newv.index('x'+n))
  import os
  xsA=find(A,tries=int(os.environ.get('TA','300')),seed=1)
  fw=[]
  for x in xsA:
    e=env(A,x); ta=target(A,x)
    if 'K' in pts and 'K' not in e: e['K']=g.Center(e['Gamma'])
    rb,okb,_=resid(B,x); tb=target(B,x)
    xc=list(x)+[q for n in pts for q in (float(e[n].x),float(e[n].y))]
    rc,okc,_=resid(C,xc); tc=target(C,xc)
    fw.append(dict(tA=ta,B_ok=okb and max(map(abs,rb))<1e-8,dB=abs(tb-ta),C_ok=okc and max(map(abs,rc))<1e-8,dC=abs(tc-ta)))
  xsC=find(C,tries=int(os.environ.get('TC','400')),seed=2)
  bw=[]
  for xc in xsC:
    xa=xc[:len(A['variables'])]
    try:
      ra,oka,e=resid(A,xa); ta=target(A,xa)
      if 'K' in pts and 'K' not in e: e['K']=g.Center(e['Gamma'])
      dpt=max(math.hypot(float(e[n].x)-xc[len(A['variables'])+2*k],float(e[n].y)-xc[len(A['variables'])+2*k+1]) for k,n in enumerate(pts))
      bw.append(dict(A_ok=oka and max(map(abs,ra))<1e-8,dT=abs(ta-target(C,xc)),dpts=dpt,tC=target(C,xc)))
    except Exception as ex: bw.append(dict(err=str(ex)[:80]))
  rep[i]=dict(forward=fw,backward=bw)
  print(i,'A->B,C:',len(fw),'ok' if fw and all(f['B_ok'] and f['C_ok'] and f['dB']<1e-9 and f['dC']<1e-9 for f in fw) else 'NG',
        '| C->A:',len(bw),'ok' if bw and all(b.get('A_ok') and b['dT']<1e-8 and b['dpts']<1e-7 for b in bw) else 'NG')
  print('  targets A:',sorted({round(f['tA'],9) for f in fw}),' C:',sorted({round(b.get('tC',0),9) for b in bw}))
json.dump(rep,open(os.devnull,'w'),indent=1)
