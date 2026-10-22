import json,glob,re,numpy as np,pandas as pd
from scipy.stats import spearmanr
import statsmodels.api as sm, statsmodels.formula.api as smf
D='/tmp/claude-0/-home-claude-geosolver/8916e0f3-f5ae-5c0a-92a1-90183b146a86/scratchpad/diff/jssa/results/difficulty-20261022'
def load(path):
    rows=[]
    for f in glob.glob(path):
        d=json.load(open(f))
        if d.get('status')!='ok' or not d['starts_done']: continue
        cid=d['case_id']; m=re.search(r'\.([kz])(\d)\.json$',d.get('dsl_override') or '')
        k=int(m.group(2)) if m else 0
        kap=np.nan
        if d['first_hit']:
            s=list(d['first_hit'].values())[0]['svals']
            if s and min(s)>0: kap=max(s)/min(s)
        rows.append(dict(base=cid,k=k,n=d['starts_done'],hits=d['counts'].get('hit',0),p=d['p_any'],kap=kap,sec=d['sec_per_start_median'],nv=d['n_vars']))
    return pd.DataFrame(rows)
x=load(D+'/probe_extra/*.json'); print(len(x), x.base.nunique())
x['logk']=np.log10(x.kap)
# within-problem deltas vs k=0
base=x[x.k==0].set_index('base')
dd=x[x.k>0].join(base[['p','logk']],on='base',rsuffix='0').dropna(subset=['logk','logk0'])
dd['dp']=dd.p-dd.p0; dd['dlk']=dd.logk-dd.logk0
r=spearmanr(dd.dlk,dd.dp)[0]; print('pairs',len(dd),'rho',round(r,3))
rng=np.random.default_rng(0); bs=[]; bases=dd.base.unique()
for _ in range(5000):
    pick=rng.choice(bases,len(bases)); s=pd.concat([dd[dd.base==b] for b in pick])
    if s.dlk.nunique()>1: bs.append(spearmanr(s.dlk,s.dp)[0])
print('cluster bootstrap 95%',np.round(np.percentile(bs,[2.5,97.5]),3))
# permutation within problems: shuffle dlk among pairs of same problem? use sign-flip of problem-level mean slope
# binomial GLM with problem fixed effects
x['miss']=x.n-x.hits
m1=smf.glm('hits+miss ~ k + C(base)',data=x,family=sm.families.Binomial()).fit(cov_type='cluster',cov_kwds={'groups':pd.factorize(x.base)[0]})
print('GLM k coef',round(m1.params['k'],3),'se',round(m1.bse['k'],3),'p',m1.pvalues['k'])
xx=x.dropna(subset=['logk'])
m2=smf.glm('hits+miss ~ k + logk + C(base)',data=xx,family=sm.families.Binomial()).fit(cov_type='cluster',cov_kwds={'groups':pd.factorize(xx.base)[0]})
print('GLM k,logk',m2.params[['k','logk']].round(3).to_dict(),m2.pvalues[['k','logk']].to_dict())
x.to_csv('/tmp/claude-0/-home-claude-geosolver/8916e0f3-f5ae-5c0a-92a1-90183b146a86/scratchpad/stats/extra.csv',index=False)
# 323: binomial GLM p ~ d + logk
y=load(D+'/probe_323/*.json'); y['logk']=np.log10(y.kap); y['miss']=y.n-y.hits
yy=y.dropna(subset=['logk'])
for f in ['nv','nv+logk','nv*logk']:
    g=smf.glm('hits+miss ~ '+f,data=yy,family=sm.families.Binomial()).fit()
    print('323',f,len(yy),g.params.round(3).to_dict(),'pseudoR2(McF)',round(1-g.llf/smf.glm('hits+miss ~ 1',data=yy,family=sm.families.Binomial()).fit().llf,3))
