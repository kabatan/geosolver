"""Aggregate every preregistered trial, including failures; no new solver work."""
from pathlib import Path
import json,csv,statistics,collections
HERE=Path(__file__).resolve().parent

def csvout(name,rows):
 with (HERE/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 cohorts=json.loads((HERE/'cohorts.json').read_text());runs=[];flat=[]
 for f in sorted((HERE/'runs').glob('*/result.json')):
  r=json.loads(f.read_text());runs.append(r)
  a=next((a for a in reversed(r.get('attempts',[])) if a.get('candidate_status')=='certified'),{})
  anycert=list(f.parent.glob('certificate*.json'))
  row={k:r.get(k,'') for k in ['id','arm','seed','status','seconds','zero_dimensional','encoding_seconds','setup_seconds','numeric_seconds','certified_P','certificate_kind','original_feasible_at_candidate']}
  row['cohort']='positive' if r['id'] in cohorts['positive_development'] else 'zero'
  row['C180']=r['seconds'] if r['status']=='certified' else 180
  row['attempts']=len(r.get('attempts',[]));row['identities_saved']=len(anycert)
  row['certificate_seconds']=a.get('certificate_seconds',r.get('elimination_and_certificate_seconds',''))
  row['check_seconds']=a.get('independent_verification_seconds',r.get('independent_verification_seconds',''))
  row['root_seconds']=a.get('root_seconds',r.get('root_seconds',''))
  row['allowed_roots']=a.get('root_check',r.get('root_check',{})).get('allowed_root_count','')
  row['accepted_from_nonadmissible']=r['status']=='certified' and r['arm']=='C2' and r.get('original_feasible_at_candidate') is False
  row['unique_candidate_failures']=';'.join(sorted(set(a.get('candidate_status','') for a in r.get('attempts',[]) if a.get('P'))))
  flat.append(row)
 csvout('per-run.csv',flat)
 pos=[]
 for cid in cohorts['positive_development']:
  q={'id':cid}
  for arm in ['C1','C2','C3']:
   rr=[r for r in flat if r['id']==cid and r['arm']==arm];ok=[r for r in rr if r['status']=='certified']
   q[arm+'_success']=f'{len(ok)}/{len(rr)}';q[arm+'_median_C180']=statistics.median(r['C180'] for r in rr)
   q[arm+'_successful_median_seconds']=statistics.median(r['seconds'] for r in ok) if ok else ''
  q['C2_vs_C1_median_reduction']=1-q['C2_median_C180']/q['C1_median_C180']
  q['C2_vs_C3_median_reduction']=1-q['C2_median_C180']/q['C3_median_C180']
  q['nonadmissible_C2_successes']=sum(r['accepted_from_nonadmissible'] for r in flat if r['id']==cid)
  pos.append(q)
 csvout('positive-summary.csv',pos)
 zs=[]
 for cid in cohorts['zero_candidates']:
  q={'id':cid}
  for arm in ['C1','C2','C3']:
   r=next(r for r in flat if r['id']==cid and r['arm']==arm)
   for k in ['status','seconds','identities_saved','allowed_roots','zero_dimensional','unique_candidate_failures']:q[arm+'_'+k]=r[k]
  zs.append(q)
 csvout('zero-summary.csv',zs)
 aggregate={}
 for cohort in ['positive','zero']:
  aggregate[cohort]={}
  for arm in ['C1','C2','C3']:
   rr=[r for r in flat if r['cohort']==cohort and r['arm']==arm];ok=[r for r in rr if r['status']=='certified']
   aggregate[cohort][arm]={'n':len(rr),'certified':len(ok),'mean_C180':statistics.mean(r['C180'] for r in rr),
    'status_counts':dict(collections.Counter(r['status'] for r in rr)),
    'identity_count':sum(r['identities_saved'] for r in rr),'time_sum':sum(r['seconds'] for r in rr),
    'successful_median_seconds':statistics.median(r['seconds'] for r in ok) if ok else None}
 zd=[r['seconds'] for r in flat if r['cohort']=='zero' and r['arm']=='C3']
 aggregate.update(trials=len(flat),new_certified_nonadmissible=sum(r["accepted_from_nonadmissible"] for r in flat),zero_C3_identity_seconds={'min':min(zd),'median':statistics.median(zd),'max':max(zd)},
   positive_large_C1_improvement=[r['id'] for r in pos if r['C2_vs_C1_median_reduction']>=.2],
   positive_large_C3_improvement=[r['id'] for r in pos if r['C2_vs_C3_median_reduction']>=.2],
   combined_large_improvement=[r['id'] for r in pos if r['C2_vs_C1_median_reduction']>=.2 and r['C2_vs_C3_median_reduction']>=.2],
   total_measured_seconds=sum(r['seconds'] for r in flat))
 (HERE/'summary.json').write_text(json.dumps(aggregate,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps(aggregate,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
