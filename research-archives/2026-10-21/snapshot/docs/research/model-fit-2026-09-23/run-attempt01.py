"""Inference-only local model screen; immutable receipts and 90min total watchdog."""
import os
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('VLLM_USE_FLASHINFER_SAMPLER','0')
os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
import argparse,json,sys,time,hashlib
from pathlib import Path
from qwen.common import write_json,file_hash,now,stable_seed
from qwen.grpo_run import run_worker
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/model_fit_20260923')

def worker(key):
 from transformers import AutoTokenizer
 from vllm import LLM,SamplingParams
 protocol=json.loads((D/'protocol.json').read_text())
 assert file_hash(D/'jobs.json')==protocol['jobs_sha256']
 model=protocol['models'][key]['snapshot']
 tokenizer=AutoTokenizer.from_pretrained(model,local_files_only=True)
 llm=LLM(model=model,dtype='float16',kv_cache_dtype='auto',enable_lora=True,max_lora_rank=32,lora_dtype='float16',max_loras=1,max_model_len=32768,max_num_seqs=4,max_num_batched_tokens=1024,gpu_memory_utilization=.85,enforce_eager=True,enable_prefix_caching=False,seed=2026092304)
 jobs=json.loads((D/'jobs.json').read_text())
 for i,row in enumerate(jobs):
  ids=tokenizer.apply_chat_template([{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':row['problem']}],tokenize=True,add_generation_prompt=True,enable_thinking=True)
  cap=min(32512,32768-len(ids))
  seed=stable_seed(2026092304,{'id':row['id'],'problem':row['problem']})%(2**31)
  t=time.monotonic()
  result=llm.generate([{'prompt_token_ids':ids}],SamplingParams(n=2,temperature=.6,top_p=.95,top_k=20,max_tokens=cap,seed=seed))[0]
  elapsed=time.monotonic()-t
  records=[]
  for sample,c in enumerate(result.outputs):
   raw=tokenizer.decode(c.token_ids,skip_special_tokens=False)
   final=raw.split('</think>',1)[1] if '</think>' in raw else ''
   records.append({**row,'model':key,'sample':sample,'prompt_ids':ids,'raw_text':raw,'final_text':final,'completion_ids':list(c.token_ids),'tokens':len(c.token_ids),'finish_reason':c.finish_reason,'seed':seed,'completion_cap':cap,'elapsed_group_seconds':elapsed})
  write_json(R/key/f'group-{i:02}.json',records)
  print(json.dumps({'job':i,'id':row['id'],'tokens':[x['tokens'] for x in records],'seconds':round(elapsed,2)},ensure_ascii=False),flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--worker',choices=['original_4b','thinking_2507']);args=ap.parse_args()
 if args.worker:return worker(args.worker)
 R.mkdir(parents=True,exist_ok=True)
 receipt=R/'receipt.json';assert not receipt.exists(),'Run immutable; inspect existing receipt'
 p=json.loads((D/'protocol.json').read_text())
 rec={'status':'running','start_utc':now(),'protocol_sha256':file_hash(D/'protocol.json'),'driver_sha256':file_hash(__file__),'updates':0,'workers':[]}
 write_json(receipt,rec);begin=time.monotonic()
 try:
  for key in ['original_4b','thinking_2507']:
   (R/key).mkdir()
   t=time.monotonic();entry={'model':key,'start_utc':now(),'status':'running'};rec['workers'].append(entry);write_json(receipt,rec)
   try:
    run_worker([sys.executable,str(Path(__file__).resolve()),'--worker',key],R/key/'generate.log',5400-(time.monotonic()-begin));entry['status']='complete'
   finally:
    entry['elapsed_seconds']=time.monotonic()-t;entry['end_utc']=now();write_json(receipt,rec)
   print(json.dumps(entry),flush=True)
  rec['status']='complete'
 except BaseException as e:
  rec['status']='failed';rec['error']=repr(e);raise
 finally:
  rec['elapsed_seconds']=time.monotonic()-begin;rec['end_utc']=now();write_json(receipt,rec)
if __name__=='__main__':main()
