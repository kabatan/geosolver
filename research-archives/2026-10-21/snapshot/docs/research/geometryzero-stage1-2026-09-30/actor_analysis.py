import json,math,statistics
from prepare import RUN,HERE,write
def stats(x):return dict(mean=statistics.mean(x),mean_abs=statistics.mean(abs(v) for v in x),max_abs=max(abs(v) for v in x),rms=math.sqrt(statistics.mean(v*v for v in x)))
def main():
 base={r['id']:r['actor_logps'] for r in json.loads((RUN/'actor-base/actor-verification.json').read_text())};out={}
 for pid in ('DA08','DA06'):
  updated={r['id']:r['actor_logps'] for r in json.loads((RUN/('actor-updated-'+pid)/'actor-verification.json').read_text())};checks=json.loads((RUN/('update-'+pid)/'fixed-probes.json').read_text());rows=json.loads((RUN/('training-'+pid+'.json')).read_text());records=[]
  for v,row in zip(checks,rows[:4],strict=True):
   b=base[v['id']];a=updated[v['id']];hb=v['before_logps'];ha=v['after_logps'];assert len(b)==len(a)==len(hb)==len(ha)
   bd=[x-y for x,y in zip(b,hb,strict=True)];ad=[x-y for x,y in zip(a,ha,strict=True)];delta=[x-y for x,y in zip(a,b,strict=True)];hdelta=[x-y for x,y in zip(ha,hb,strict=True)];disagreement=[x-y for x,y in zip(delta,hdelta,strict=True)]
   records.append(dict(id=v['id'],tokens=len(a),advantage=row['advantage'],reward=row['total_reward'],base_actor_learner=stats(bd),updated_actor_learner=stats(ad),actor_update_delta=stats(delta),learner_update_delta=stats(hdelta),update_delta_disagreement=stats(disagreement)))
  receipt=json.loads((RUN/('update-'+pid)/'receipt.json').read_text());rawfidelity=receipt['actor_learner'];prefixfidelity=[r['base_actor_learner'] for r in records]
  out[pid]=dict(checks=records,raw_actor_learner_mean_abs_max=max(r['mean_abs'] for r in rawfidelity),raw_actor_learner_max_abs=max(r['max_abs'] for r in rawfidelity),raw_previous_gate_pass=all(r['mean_abs']<=.02 and r['max_abs']<=.2 for r in rawfidelity),fixed_prefix_previous_gate_pass=all(r['mean_abs']<=.02 and r['max_abs']<=.2 for r in prefixfidelity),actor_direction_agreement=sum(r['actor_update_delta']['mean']*r['advantage']>0 for r in records),learner_direction_agreement=sum(r['learner_update_delta']['mean']*r['advantage']>0 for r in records),scope='Four prefixes max256 per group; directions descriptive, correlated gradients and quantization mean per-answer sign is not a correctness test; regenerated same training question eight answers are connection checks, not gain/transfer.')
 write(HERE/'actor-connection.json',out);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
