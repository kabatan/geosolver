"""Additional descriptive breakdown, without changing frozen rewards/selection."""
import json,statistics
from prepare import HERE,RUN,write
from signals import normalize
def main():
 rows=json.loads((RUN/'scores.json').read_text());labels=json.loads((RUN/'labels.json').read_text());groups=[]
 for pid in labels:
  rr=[r for r in rows if r['problem_id']==pid and r['group']=='main'];allnatural=not any(r['censored'] for r in rr);vals={}
  if allnatural:
   vals['numeric']=[r['relaxed'] for r in rr];vals['numeric_format']=[r['relaxed']+r['format'] for r in rr]
   if all('total_reward' in r for r in rr):vals['full']=[r['total_reward'] for r in rr]
  groups.append(dict(id=pid,natural=allnatural,components={k:dict(std=statistics.stdev(v),mixed=statistics.stdev(v)>0,nonzero_advantages=sum(abs(a)>1e-8 for a in normalize(v))) for k,v in vals.items()},incorrect_positive_full_advantages=[r['sample'] for r in rr if r['relaxed']==0 and r.get('advantage',0)>0],correct_negative_full_advantages=[r['sample'] for r in rr if r['relaxed']==1 and r.get('advantage',0)<0]))
 result=dict(groups=groups,mixed_counts={k:sum(g['components'].get(k,{}).get('mixed',False) for g in groups) for k in ('numeric','numeric_format','full')},incorrect_positive_full_advantages=sum(len(g['incorrect_positive_full_advantages']) for g in groups),correct_negative_full_advantages=sum(len(g['correct_negative_full_advantages']) for g in groups),empty_auxiliary_tags=sum(bool(__import__('re').search(r'<auxiliary>\s*</auxiliary>',r['raw_text'])) for r in rows if r['group']=='main'),scope='Censor-aware; full requires an identified mask. Diagnostics do not rescore training.')
 write(HERE/'signal-diagnostics.json',result);print(json.dumps({k:v for k,v in result.items() if k!='groups'},indent=2))
if __name__=='__main__':main()
