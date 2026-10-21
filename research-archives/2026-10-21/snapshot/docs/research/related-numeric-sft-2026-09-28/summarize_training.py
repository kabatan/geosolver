from pathlib import Path
import json,statistics,hashlib
P=Path(__file__).resolve().parent;R=P.parents[2];O=R/'qwen/.runtime/related_numeric_sft_20260928'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
out={}
for arm in ['sft-a','sft-b']:
 a=read(O/f'{arm}-train32/receipt.json');b=read(O/f'{arm}-train128/receipt.json');assert a['status']==b['status']=='complete'
 final=read(O/f'{arm}-train128/final/receipt.json');assert final['global_updates']==final['optimizer_step_min']==final['optimizer_step_max']==128
 assert a['global_updates']==32 and b['updates']==96 and a['examples_processed']+b['examples_processed']==512
 assert b['prior_adapter_sha256']==a['adapter_sha256'] and b['prior_optimizer_sha256']==a['optimizer_sha256']
 assert a['dataset_sha256']==b['dataset_sha256']==sha(O/'train.json')
 rows=[]
 for stage in [32,128]:rows.extend(json.loads(s) for s in (O/f'{arm}-train{stage}/examples.jsonl').read_text().splitlines())
 assert len(rows)==512 and len({r['position'] for r in rows})==512
 first={};last={};count={}
 for r in rows:first.setdefault(r['id'],r['loss']);last[r['id']]=r['loss'];count[r['id']]=count.get(r['id'],0)+1
 out[arm]={'global_updates':128,'training_seed':b['training_parameters']['seed'],'examples_presented':512,'unique_examples':80,'target_tokens':sum(r['target_tokens'] for r in rows),'presentations_min':min(count.values()),'presentations_max':max(count.values()),'first_presentation_mean_loss':statistics.mean(first.values()),'last_presentation_mean_loss':statistics.mean(last.values()),'examples_with_lower_last_loss':sum(last[k]<first[k] for k in first),'training_seconds':a['elapsed_seconds']+b['elapsed_seconds'],'peak_allocated_gib':max(a['peak_allocated_gib'],b['peak_allocated_gib']),'adapter_sha256':b['adapter_sha256'],'optimizer_steps_verified':True,'by_source':{s:{'first_mean_loss':statistics.mean(first[r['id']] for r in rows[:80] if r['source_id']==s),'last_mean_loss':statistics.mean(last[r['id']] for r in rows[:80] if r['source_id']==s)} for s in sorted({r['source_id'] for r in rows})}}
(O/'training-summary.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
