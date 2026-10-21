"""Descriptive calibration and transparent serial time extrapolation."""
import json,statistics
from prepare import RUN,HERE,write
def main():
 s=json.loads((RUN/'signal-summary.json').read_text());rows=json.loads((RUN/'scores.json').read_text());ds=s['groups'];out={}
 for group in ('main','with','without'):
  rr=[r for r in rows if r['group']==group];natural=[r for r in rr if not r['censored']];correct=[r for r in natural if r['relaxed']==1]
  out[group]=dict(total=len(rr),natural=len(natural),censored=len(rr)-len(natural),relaxed_correct=sum(r['relaxed']==1 for r in natural),strict_correct=sum(r['strict']==1 for r in natural),exact_correct=sum(r['exact']==1 for r in natural),format_count=sum(r['format']>0 for r in natural),aux_count=sum(r['aux']>0 for r in natural),unparsed=sum(r['parsed'] is None for r in natural),total_tokens=sum(len(r['completion_ids']) for r in rr),mean_tokens=statistics.mean(len(r['completion_ids']) for r in rr),relaxed_only_samples=[dict(id=r['id'],sample=r['sample'],parsed=r['parsed'],relative_error=r['relative_error']) for r in correct if r['strict']==0])
 out['questions']=dict(total=len(ds),main_numeric_mixed=sum(d['numeric_mixed'] for d in ds),main_full_mixed=sum(d['full_mixed'] for d in ds),main_natural=sum(d['main_natural'] for d in ds),numeric_uniform_full_mixed=sum(d['full_mixed'] and not d['numeric_mixed'] for d in ds),masks={str(m):sum(d['mask']==m for d in ds) for m in (-1,0,1,None)},extensions=s['extension_ids'],selected=s['selected_updates'],selection_kind=s['selection_kind'])
 for stage in ('screen1024','screen2048'):
  p=RUN/stage/'receipt.json'
  if p.exists():
   receipt=json.loads(p.read_text());rr=[json.loads(f.read_text()) for f in p.parent.glob('*-*.json')];out[stage]=dict(receipt=receipt,groups=len(rr),generation_seconds=sum(r[0]['generation_seconds_group'] for r in rr),tokens=sum(len(r['completion_ids']) for rs in rr for r in rs),censored=sum(r['finish_reason']!='stop' for rs in rr for r in rs))
 out['update_measurements']={}
 for p in RUN.glob('update-*/receipt.json'):out['update_measurements'][p.parent.name]=json.loads(p.read_text())
 # Cost is the dataset scale, not number of independent configurations.
 seconds_by_question=[sum(g['seconds'] for g in d['groups'].values()) for d in ds];out['generation_projection']=dict(per_question_mean_seconds=statistics.mean(seconds_by_question),per_question_min_seconds=min(seconds_by_question),per_question_max_seconds=max(seconds_by_question),one_pass148_hours=statistics.mean(seconds_by_question)*148/3600,four_pass592_hours=statistics.mean(seconds_by_question)*592/3600,scope='Three groups of eight; caps selected by first-stage protocol; excludes engine load and update; current 24 originals do not measure scaled variants difficulty.')
 times=[r['forward_backward_seconds']+r['old_logp_seconds']+r['optimizer_seconds'] for r in out['update_measurements'].values() if r['status']=='complete']
 if times:out['training_projection']=dict(per_question_seconds_measured=times,one_pass148_hours_range=[min(times)*148/3600,max(times)*148/3600],four_pass592_hours_range=[min(times)*592/3600,max(times)*592/3600],scope='One-question optimizer steps. Paper batch32 throughput and optimizer amortization are unmeasured. Loads/saves/reloads excluded.')
 write(HERE/'measurements.json',out);print(json.dumps(out,indent=2))
 positive=[dict(id=r['id'],sample=r['sample'],answer=r['parsed'],strict=r['strict'],source=r['source'],text=r['raw_text']) for r in rows if r['group']=='main' and r['relaxed']==1];write(HERE/'positive-main-review.json',positive)
if __name__=='__main__':main()
