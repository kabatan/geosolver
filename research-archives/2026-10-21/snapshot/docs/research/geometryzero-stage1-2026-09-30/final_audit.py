"""Integrity of completed finite stage; absence of leaks is input-level only."""
import json
from prepare import HERE,RUN,ROOT,sha,write
def main():
 from transformers import AutoTokenizer
 model=json.loads((HERE/'model.json').read_text());tok=AutoTokenizer.from_pretrained(model['snapshot'],local_files_only=True);jobs=json.loads((RUN/'jobs.json').read_text());labels=json.loads((RUN/'labels.json').read_text());selection=json.loads((HERE/'selection.json').read_text());assert len(jobs)==72 and len(labels)==24 and list(labels)==selection['ids']
 assert sha(RUN/'jobs.json')==selection['jobs_sha256'] and sha(RUN/'labels.json')==selection['labels_sha256'];assert sha(ROOT/'benchmarks/humpty_configurations_v2/training_variants.jsonl')==selection['dataset_sha256']
 total=0;tokens=0;censor=0;main_censor=0;extensions=[]
 for j in jobs:
  assert not set(j)&{'answer','answer_exact','target','reference'};p=RUN/'screen1024'/(j['id']+'.json');rr=json.loads(p.read_text());assert len(rr)==8 and {r['sample'] for r in rr}==set(range(8));ids=tok.encode(tok.apply_chat_template(j['messages'],tokenize=False,add_generation_prompt=True),add_special_tokens=False)
  assert all(r['messages']==j['messages'] and r['prompt_ids']==ids and len(r['rollout_logps'])==len(r['completion_ids']) and len(r['completion_ids'])<=1024 and tok.decode(r['completion_ids'],skip_special_tokens=False)==r['raw_text'] for r in rr)
  total+=8;tokens+=sum(len(r['completion_ids']) for r in rr);c=sum(r['finish_reason']!='stop' for r in rr);censor+=c
  if j['group']=='main':main_censor+=c
  if j['group']=='main' and c>=4:extensions.append(j['problem_id'])
 assert total==576 and not extensions
 frozen=json.loads((HERE/'update-freeze.json').read_text());assert all(sha(HERE/f)==h for f,h in frozen.items());assert sha(HERE/'rollout-screen-frozen.py')==json.loads((RUN/'screen1024/receipt.json').read_text())['source_sha256']
 summaries=json.loads((RUN/'signal-summary.json').read_text());assert summaries['selected_updates']==['DA08','DA06'];updates={}
 for pid in summaries['selected_updates']:
  receipt=json.loads((RUN/('update-'+pid)/'receipt.json').read_text());assert receipt['status']=='complete' and receipt['actual_updates']==1 and receipt['optimizer_steps']==[1] and receipt['changed_tensors']>0 and receipt['saved_tensors_verified']>0;assert receipt['source_sha256']==sha(HERE/'full_update.py') and receipt['rows_sha256']==sha(RUN/('training-'+pid+'.json'));updates[pid]=receipt['actual_updates']
 for name in ['actor-base','actor-updated-DA08','actor-updated-DA06','fp16-actor-base','fp16-actor-DA08','fp16-actor-DA06']:assert json.loads((RUN/name/'receipt.json').read_text())['status']=='complete'
 hashes={str(p.relative_to(RUN)):sha(p) for p in RUN.rglob('*') if p.is_file() and 'reward-deps' not in p.parts and p.suffix in ('.json','.safetensors','.pt')}
 write(HERE/'artifact-manifest.json',hashes);write(HERE/'final-audit.json',dict(status='pass',questions=24,groups=72,answers=total,completion_tokens=tokens,censored=censor,main_censored=main_censor,extension_ids=extensions,updates=updates,scope='Finite stage integrity and recorded execution. Does not certify mathematical proofs, RL convergence, BF16 fidelity or FP16 training.'))
 print(json.dumps(dict(status='pass',answers=total,tokens=tokens,updates=updates)))
if __name__=='__main__':main()
