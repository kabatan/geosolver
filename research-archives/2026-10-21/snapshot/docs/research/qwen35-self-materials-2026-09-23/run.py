"""Immutable no-update Qwen3.5-9B inference for the materials pilot."""
import os
os.environ.setdefault('HF_HUB_OFFLINE','1');os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('VLLM_USE_FLASHINFER_SAMPLER','0');os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
import argparse,json,sys,time
from pathlib import Path
from qwen.common import write_json,file_hash,now
from qwen.grpo_run import run_worker
D=Path(__file__).resolve().parent;R=Path('qwen/.runtime/qwen35_self_materials_20260923')
def worker(a):
 from transformers import AutoTokenizer
 from vllm import LLM,SamplingParams
 p=json.loads((D/'protocol.json').read_text());meta=json.loads((D/'model.json').read_text());jobs=json.loads(Path(a.jobs).read_text())
 tok=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True)
 prompts=[];texts=[];params=[]
 for row in jobs:
  text=tok.apply_chat_template(row['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=False)
  ids=tok.encode(text,add_special_tokens=False)
  assert len(ids)+p['max_output_tokens']<=p['max_context'],(row['id'],len(ids))
  prompts.append(dict(prompt_token_ids=ids));texts.append(text)
  params.append(SamplingParams(n=1,**p['sampling'],seed=row['seed'],max_tokens=p['max_output_tokens']))
 write_json(Path(a.out)/'token-preflight.json',[dict(id=j['id'],tokens=len(x['prompt_token_ids']),seed=j['seed']) for j,x in zip(jobs,prompts)])
 m=LLM(model=meta['snapshot'],dtype=p['dtype'],kv_cache_dtype=p['kv_cache_dtype'],max_model_len=p['max_context'],max_num_seqs=p['max_num_seqs'],max_num_batched_tokens=p['max_num_batched_tokens'],gpu_memory_utilization=p['gpu_memory_utilization'],enforce_eager=True,enable_prefix_caching=False,language_model_only=True,seed=2026092337)
 start=time.monotonic();outputs=m.generate(prompts,params);duration=time.monotonic()-start
 for row,inp,text,res in zip(jobs,prompts,texts,outputs):
  assert list(res.prompt_token_ids)==inp['prompt_token_ids']
  c=res.outputs[0];raw=tok.decode(c.token_ids,skip_special_tokens=False)
  final=raw.split('</think>',1)[-1] if '</think>' in raw else raw
  write_json(Path(a.out)/(row['id']+'.json'),row|dict(model=meta['model_id'],revision=meta['revision'],prompt_text=text,prompt_ids=inp['prompt_token_ids'],raw_text=raw,final_text=final,completion_ids=list(c.token_ids),tokens=len(c.token_ids),finish_reason=c.finish_reason,batch_generation_seconds=duration))
  print(json.dumps(dict(id=row['id'],tokens=len(c.token_ids),finish=c.finish_reason)),flush=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--jobs',required=True);ap.add_argument('--phase',required=True);ap.add_argument('--worker',action='store_true');ap.add_argument('--out');a=ap.parse_args()
 if a.worker:return worker(a)
 out=R/a.phase;out.mkdir(parents=True,exist_ok=False)
 rec=dict(status='running',start_utc=now(),updates=0,jobs_sha256=file_hash(a.jobs),protocol_sha256=file_hash(D/'protocol.json'),driver_sha256=file_hash(__file__),phase=a.phase)
 write_json(out/'receipt.json',rec);t=time.monotonic()
 try:
  run_worker([sys.executable,str(Path(__file__).resolve()),'--worker','--jobs',str(Path(a.jobs).resolve()),'--phase',a.phase,'--out',str(out)],out/'generate.log',3600)
  rec['status']='complete'
 except BaseException as e:rec.update(status='failed',error=repr(e));raise
 finally:rec.update(elapsed_seconds=time.monotonic()-t,end_utc=now());write_json(out/'receipt.json',rec);print(json.dumps(rec),flush=True)
if __name__=='__main__':main()
