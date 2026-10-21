"""Final provenance and precision comparison; pass does not mean policy fidelity."""
import hashlib,json,math,statistics,sys,time
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def stats(v):return dict(mean_abs=statistics.mean(map(abs,v)),max_abs=max(map(abs,v)),rms=math.sqrt(statistics.mean(x*x for x in v)))
def main():
 r=Path(sys.argv[1]).resolve()
 for n in ('freeze.json','importance-amendment-freeze.json','controlled-actor-freeze.json','precision-diagnostic-freeze.json'):
  for p,h in read(r/n)['sha256'].items():assert sha(p)==h,(n,p)
 for p,h in read(r/'implementation-freeze.json')['sha256'].items():
  if Path(p).name=='test_probe.py':assert sha(p)==read(r/'cpu-validation.json')['test_source_sha256']
  else:assert sha(p)==h,('implementation-freeze.json',p)
 original_actor=read(r/'actor-verification-freeze.json');assert sha(original_actor['implementation'])==original_actor['source_sha256']
 mechanical=read(r/'mechanical-audit.json');technical=read(r/'technical-audit.json')
 assert mechanical['status']==technical['status']=='pass'
 for p,h in mechanical['source_hashes'].items():assert sha(p)==h
 actor=read(r/'precision-fp16-actor/actor-verification.json');learner=read(r/'precision-fp16-learner/verification.json')
 ar=read(r/'precision-fp16-actor/receipt.json');lr=read(r/'precision-fp16-learner/receipt.json')
 assert ar['status']==lr['status']=='complete' and ar['generation_seconds']==lr['actual_updates']==0
 assert ar['adapter_sha256']==technical['probes'][0]['receipt']['vllm_adapter_sha256']
 assert lr['adapter_sha256']==technical['probes'][0]['receipt']['adapter_sha256']
 assert ar['verification_sha256']==lr['verification_sha256']==sha(r/'probe-short-tis/fixed-probes.json')
 assert ar['driver_sha256']==sha(Path(__file__).with_name('precision_actor.py'))
 assert lr['source_sha256']==sha(Path(__file__).with_name('precision_learner.py'))
 ad=[];ld=[];br=[];ur=[];zero=[]
 assert len(actor)==len(learner)==4
 for x,y in zip(actor,learner):
  assert x['id']==y['id']
  ab,aa,lb,la=x['actor_before_logps'],x['actor_after_logps'],y['before_logps'],y['after_logps']
  assert len(ab)==len(aa)==len(lb)==len(la)==1024
  assert all(math.isfinite(v) for v in ab+aa+lb+la)
  ad.extend(v-u for u,v in zip(ab,aa));ld.extend(v-u for u,v in zip(lb,la))
  br.extend(v-u for v,u in zip(ab,lb));ur.extend(v-u for v,u in zip(aa,la))
  zero.extend(v-u for v,u in zip(ab,x['actor_unadapted_logps']))
 comparison=dict(scope='same BF16-trained checkpoint, FP16 teacher forcing only; no FP16 update or generation',completion_tokens=len(ad),actor_delta=stats(ad),learner_delta=stats(ld),base_backend_residual=stats(br),updated_backend_residual=stats(ur),zero_lora_vs_no_lora_delta=stats(zero),delta_residual=stats([a-b for a,b in zip(ad,ld)]),delta_cosine=sum(a*b for a,b in zip(ad,ld))/math.sqrt(sum(a*a for a in ad)*sum(b*b for b in ld)),bf16_delta_cosine=technical['actor']['delta_cosine'],interpretation='FP16 lowers absolute backend residual but does not establish agreement of the update direction; fidelity remains unresolved')
 (r/'precision-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
 notes=read(r/'actor-math-review.json');rows=read(r/'actor-reload/simple-H04.json');assert len(notes)==len(rows)==4
 for n,row in zip(notes,rows):
  assert n['raw_file_sha256']==sha(n['raw_file'])
  assert n['raw_text_sha256']==hashlib.sha256(row['raw_text'].encode()).hexdigest()
  assert n['read_characters']==len(row['raw_text']) and row['finish_reason']=='stop'
  assert row['policy_adapter_sha256']==technical['actor']['receipt']['adapter_sha256']
 guard=Path('qwen/.runtime/program_self_training_20260926').resolve();guards=[]
 for label in ('screen16384','screen16384-retry','screen32768','probe-short','probe-long','probe-short-tis','probe-long-tis','actor-reload','precision-fp16-actor','precision-fp16-learner'):
  p=guard/('rl-feasibility-20260930-'+label)/'receipt.json'
  if p.exists():
   g=read(p);assert g['status'] in ('complete','failed') and g.get('end_unix') and g.get('returncode') is not None,(p,g)
   guards.append(dict(path=str(p),sha256=sha(p)))
 sources={str(p):sha(p) for p in Path(__file__).parent.glob('*.py')}
 artifacts={str(r/p):sha(r/p) for p in ('mechanical-audit.json','technical-audit.json','precision-comparison.json','cost-projection.json','actor-math-review.json','historical-rl-audit.json')}
 out=dict(status='pass',unix=time.time(),scope='provenance/receipt/review binding only; original fidelity gates failed and update-direction agreement remains unresolved',original_fidelity_gate=technical['original_fidelity_gate'],precision=comparison,source_hashes=sources,artifact_hashes=artifacts,guard_receipts=guards)
 (r/'final-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(status=out['status'],precision=comparison,guard_receipts=len(guards)),indent=2))
if __name__=='__main__':main()
