import json,glob,re,numpy as np,pandas as pd
from scipy.stats import wilcoxon
S='/tmp/claude-0/-home-claude-geosolver/8916e0f3-f5ae-5c0a-92a1-90183b146a86/scratchpad'
D=S+'/diff/jssa/results/difficulty-20261022/probe_extra'
def rd(f):
    d=json.load(open(f))
    if d.get('status')!='ok' or not d['starts_done']: return None
    kap=np.nan
    if d['first_hit']:
        s=list(d['first_hit'].values())[0]['svals']
        if s and min(s)>0: kap=max(s)/min(s)
    c=d['counts'];n=d['starts_done']
    return dict(n=n,p=d['p_any'],kap=kap,sec=d['sec_per_start_median'],stuck=c.get('stuck',0)/n,left=c.get('left_box',0)/n)
rows=[]
for f in glob.glob(S+'/zexp/out/*.json'):
    m=re.match(r'(.*)\.z(\d)\.json',f.split('/')[-1]); b,k=m.group(1),int(m.group(2))
    r={'base':b,'k':k}
    for cond,path in [('rand',f'{S}/initexp/rand/{b}.k{k}.json'),('init',f'{S}/initexp/init/{b}.k{k}.json'),('z',f),('k0',f'{D}/{b}.k0.json')]:
        try: x=rd(path)
        except FileNotFoundError: x=None
        if x:
            for kk,v in x.items(): r[f'{cond}_{kk}']=v
    rows.append(r)
df=pd.DataFrame(rows).sort_values(['base','k'])
pd.set_option('display.width',250)
print(df[['base','k','k0_p','rand_p','init_p','z_p','rand_n','init_n','z_n','init_kap','z_kap']].round(2).to_string())
for k in [1,2,3]:
    s=df[df.k==k]
    print(k,'median p k0/rand/init/z',[round(s[c].median(),2) for c in ['k0_p','rand_p','init_p','z_p']],'kap init/z',[round(s[c].median(),1) for c in ['init_kap','z_kap']],'sec',[round(s[c].median(),3) for c in ['k0_sec','rand_sec','init_sec','z_sec']])
ok=df.dropna(subset=['init_p','z_p'])
print('z-init median diff',round((ok.z_p-ok.init_p).median(),3),'z>init',(ok.z_p>ok.init_p).sum(),'z<init',(ok.z_p<ok.init_p).sum(),'n',len(ok), wilcoxon(ok.z_p,ok.init_p))
ok2=df.dropna(subset=['k0_p','z_p']); print('z vs k0 diff median',round((ok2.z_p-ok2.k0_p).median(),3),(ok2.z_p<ok2.k0_p).sum(),(ok2.z_p>ok2.k0_p).sum())
df.to_csv(S+'/stats/zexp.csv',index=False)
