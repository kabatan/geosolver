"""Prepare answer-free worker inputs and a read-only historical audit. No search."""
from pathlib import Path
import csv,json,hashlib,statistics,shutil,sys,importlib
import sympy as sp
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE/'vendor'))
from algebraize import translate
from run_exact import build

def save(path,obj):
 path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str)+'\n')

def main():
 cases=[json.loads(s) for s in (ROOT/'benchmarks/cases.jsonl').read_text().splitlines()]
 inputs=HERE/'inputs'; inputs.mkdir(exist_ok=True)
 manifest=[]
 for c in cases:
  raw=json.dumps({'id':c['id'],'dsl':c['dsl']},sort_keys=True,ensure_ascii=False)+'\n'
  (inputs/(c['id']+'.json')).write_text(raw)
  manifest.append({'id':c['id'],'sha256':hashlib.sha256(raw.encode()).hexdigest()})
 save(HERE/'input-manifest.json',manifest)
 basins={r['id']:r for r in csv.DictReader((ROOT/'jssa/difficulty/minima/basins-323.csv').open())}
 profile={}
 for r in csv.DictReader((ROOT/'jssa/results/stage-profile-20261023/per-case.csv').open()):
  profile.setdefault(r['case_id'],[]).append(float(r['wall_time_s']))
 old=list(csv.DictReader((HERE/'audit_source/out/batch-summary.csv').open()))
 byid={c['id']:c['dsl'] for c in cases}; audit=[]
 for r in old:
  if r['status'] not in ('identity_P','identity_E'): continue
  cid=r['id']; b=basins[cid]; dsl=byid[cid]
  p=sp.sympify(r['elim']); x=next(iter(p.free_symbols)); roots=sp.Poly(p,x).intervals(eps=sp.Rational(1,10**12))
  positive=sum(1 for (lo,hi),m in roots if lo>0 or hi>0)
  sys_,target=translate(dsl,mode='fresh',with_target=True)
  _,_,nd=build(sys_,True)
  q={'id':cid,'old_certificate':r['status'],'basin_p':b['p'],'hard_p_le_0.1':float(b['p'])<=.1,
     'n_starts':b['n_starts'],'n_vars_dsl':len(dsl['variables']),'old_singular_seconds':r['seconds'],
     'profile_wall_median':statistics.median(profile[cid]) if cid in profile else '',
     'old_P':r['P_coeffs'],'E_positive_distinct_roots':positive,
     'target':dsl['target'],'nondeg_factors':'; '.join(map(str,nd)),
     'direct_input':'unverified (246-ID audit not located)',
     'provenance':'README says solver PSLQ; CLI takes coefficients; jobs.txt absent'}
  audit.append(q)
 with (HERE/'audit-24.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(audit[0]));w.writeheader();w.writerows(audit)
 save(HERE/'audit-summary.json',{'n':len(audit),'P':sum(r['old_certificate']=='identity_P' for r in audit),
  'E':sum(r['old_certificate']=='identity_E' for r in audit),
  'low_p':[r['id'] for r in audit if r['hard_p_le_0.1']],
  'positive_unique_E':[r['id'] for r in audit if r['old_certificate']=='identity_E' and r['E_positive_distinct_roots']==1],
  'median_p':statistics.median(float(r['basin_p']) for r in audit)})
 # Select a modest zero-dimensional diagnostic cohort BEFORE any local search.
 excluded={r['id'] for r in old}; zerocandidates=[]; rejected=[]
 for cid in sorted(byid):
  d=byid[cid]
  if cid in excluded or not 1<=len(d['variables'])<=3: continue
  try:
   sy,t=translate(d,mode='fresh',with_target=True);eq,vs,nd=build(sy,True)
   if len(vs)>10 or max(sp.Poly(e,*vs).total_degree() for e in eq)>4:
    rejected.append({'id':cid,'reason':'size filter'});continue
   zerocandidates.append(cid)
   if len(zerocandidates)==12:break
  except Exception as e: rejected.append({'id':cid,'reason':type(e).__name__+':'+str(e)})
 pos=['HMMT-2013-FEB-GEO-02','HMMT-2008-FEB-GEO-06','AIME-2013-I-03','HMMT-2013-FEB-GEO-08','HMMT-2022-FEB-GEO-01','AIME-2015-II-11','aime-2001-1-9']
 save(HERE/'cohorts.json',{'positive_development':pos,'zero_candidates':zerocandidates,'size_filter_rejections':rejected})
 env={'python':sys.version,'binaries':{n:shutil.which(n) for n in ['Singular','singular','msolve']},'modules':{}}
 for name in ['sympy','mpmath','numpy','scipy','singular','msolve']:
  try: m=importlib.import_module(name);env['modules'][name]=getattr(m,'__version__','present')
  except ImportError:env['modules'][name]='absent'
 save(HERE/'environment.json',env)
 print(json.dumps({'audit':len(audit),'zero_candidates':zerocandidates,'rejected':len(rejected)},ensure_ascii=False))
if __name__=='__main__':main()
