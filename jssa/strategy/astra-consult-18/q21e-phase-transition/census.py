"""Read existing public development data only. No solver or sealed data access."""
from pathlib import Path
import csv,json,hashlib,math,collections
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

def rows(p): return list(csv.DictReader(p.open()))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def num(x):
    try:return float(x)
    except (TypeError,ValueError):return None
basinpath=ROOT/'jssa/difficulty/minima/basins-323.csv'
humanpath=ROOT/'jssa/difficulty/ghost-1023/human_feat.csv'
casepath=ROOT/'benchmarks/cases.jsonl'
basins=rows(basinpath); feats={r['case_id']:r for r in rows(humanpath)}
cases={r['id']:r for r in map(json.loads,casepath.open())}
bins=[(0,1,'<1'),(1,1.25,'1--1.25'),(1.25,1.5,'1.25--1.5'),(1.5,1.75,'1.5--1.75'),(1.75,2,'1.75--2'),(2,math.inf,'>=2')]
output=[]; rawhashes={}
for b in basins:
    cid=b['id']; d=int(b['n_vars']); f=feats.get(cid,{})
    path=ROOT/'jssa/difficulty/minima/raw-323'/f'{cid}.json'
    raw=json.loads(path.read_text()) if path.exists() else {}
    if path.exists():rawhashes[str(path.relative_to(ROOT))]=sha(path)
    dh=cases.get(cid,{}).get('dsl',{})
    meq=int(f['n_eq']) if f else sum(x.get('operator')=='=' for x in dh.get('conditions',[]))
    alpha=meq/d if d else None
    hit=sorted(raw.get('first_hit',{}).values(),key=lambda r:r.get('k',10**9))
    sv=hit[0].get('svals',[]) if hit else []
    rnk=int(sum(s>max(sv)*1e-8 for s in sv)) if sv else None
    output.append({'id':cid,'d':d,'n_eq':meq,'n_constraints_native':raw.get('n_constraints'),'alpha_eq':alpha,'density_bin':next((label for lo,hi,label in bins if alpha is not None and lo<=alpha<hi),'d=0'),'p':num(b['p']),'human':num(f.get('human')),'contest':f.get('contest'),'rank_at_first_hit':rnk,'rank_status':'observed' if sv else ('d=0' if d==0 else 'no_saved_hit_or_svals'),'first_hit_k':hit[0].get('k') if hit else None,'dsl_eq_count':sum(x.get('operator')=='=' for x in dh.get('conditions',[]))})
with (HERE/'competition-census.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
agg=[]
for lo,hi,label in bins:
    z=[r for r in output if r['density_bin']==label]
    p=[r['p'] for r in z if r['p'] is not None]
    agg.append({'bin':label,'n':len(z),'p_mean':float(np.mean(p)) if p else None,'p_median':float(np.median(p)) if p else None,'p_ge_08':sum(r['p']>=.8 for r in z if r['p'] is not None),'human_observed':sum(r['human'] is not None for r in z)})
active=[r for r in output if r['d']>0]
observed=[r for r in active if r['rank_at_first_hit'] is not None]
summary={'all_n':len(output),'active_n':len(active),'d0':len(output)-len(active),'d_distribution':dict(sorted(collections.Counter(r['d'] for r in output).items())),'alpha_eq_median':float(np.median([r['alpha_eq'] for r in active])),'bins':agg,'rank_observed':len(observed),'rank_full':sum(r['rank_at_first_hit']==r['d'] for r in observed),'rank_deficient':sum(r['rank_at_first_hit']<r['d'] for r in observed),'rank_unobserved':len(active)-len(observed),'human_by_contest':{c:sum(r['human'] is not None and r['contest']==c for r in output) for c in sorted({r['contest'] for r in output if r['contest']})},'active_human_by_contest':{c:sum(r['human'] is not None and r['contest']==c for r in active) for c in sorted({r['contest'] for r in active if r['contest']})},'eq_count_mismatches':sum(r['n_eq']!=r['dsl_eq_count'] for r in output),'native_count_mismatches':sum(r['n_constraints_native']!=r['n_eq'] for r in active)}
(HERE/'competition-summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
(HERE/'input-hashes.json').write_text(json.dumps({'inputs':{str(p.relative_to(ROOT)):sha(p) for p in [basinpath,humanpath,casepath]},'raw':rawhashes},indent=2)+'\n')
print(json.dumps(summary,indent=2,ensure_ascii=False))
