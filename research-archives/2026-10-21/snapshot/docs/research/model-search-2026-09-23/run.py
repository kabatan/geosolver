import os
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('VLLM_USE_FLASHINFER_SAMPLER','0')
os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
import argparse,json,sys,time
from pathlib import Path
from qwen.common import write_json,file_hash,now,stable_seed
from qwen.grpo_run import run_worker
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/model_search_20260923')
def worker(key,out,jobs_path):
 from transformers import AutoTokenizer
 from vllm import LLM,SamplingParams
 model=json.loads((D/(key+'-model.json')).read_text());assert model['status']=='complete'
 tokenizer=AutoTokenizer.from_pretrained(model['snapshot'],local_files_only=True)
 kwargs=dict(model=model['snapshot'],dtype='bfloat16',kv_cache_dtype='auto',max_model_len=32768,max_num_seqs=2,max_num_batched_tokens=1024,gpu_memory_utilization=.85,enforce_eager=True,enable_prefix_caching=False,seed=2026092317)
 if key.startswith('qwen35'):kwargs['language_model_only']=True
 if key=='nemotron9b':kwargs['mamba_ssm_cache_dtype']='float32'
 llm=LLM(**kwargs)
 for i,row in enumerate(json.loads(jobs_path.read_text())):
  messages=([{'role':'system','content':'/think'}] if key=='nemotron9b' else [])+[{'role':'user','content':row['problem']}]
  prompt=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=True)
  ids=tokenizer.encode(prompt,add_special_tokens=False);assert all(isinstance(x,int) for x in ids)
  cap=min(32000,32768-len(ids));seed=stable_seed(2026092317,{'id':row['id'],'problem':row['problem']})%(2**31)
  start=time.monotonic();r=llm.generate([{'prompt_token_ids':ids}],SamplingParams(n=2,temperature=.6,top_p=.95,top_k=-1,max_tokens=cap,seed=seed))[0];seconds=time.monotonic()-start
  records=[]
  for sample,c in enumerate(r.outputs):
   raw=tokenizer.decode(c.token_ids,skip_special_tokens=False)
   if '</think>' in raw:final=raw.split('</think>',1)[1];method='after_think'
   elif '<think>' in prompt or '<think>' in raw:final='';method='no_think_close'
   else:final=raw;method='raw_no_think_tag'
   records.append({**row,'model':key,'revision':model['revision'],'sample':sample,'prompt_text':prompt,'prompt_ids':ids,'completion_ids':list(c.token_ids),'raw_text':raw,'final_text':final,'extraction_method':method,'tokens':len(c.token_ids),'finish_reason':c.finish_reason,'seed':seed,'completion_cap':cap,'elapsed_group_seconds':seconds})
  write_json(out/f'group-{i:02}.json',records)
  print(json.dumps({'model':key,'id':row['id'],'tokens':[x['tokens'] for x in records],'finish':[x['finish_reason'] for x in records],'seconds':seconds}),flush=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--worker');ap.add_argument('--key');ap.add_argument('--out');ap.add_argument('--jobs',default=str(D/'jobs.json'));args=ap.parse_args()
 if args.worker:return worker(args.worker,Path(args.out),Path(args.jobs))
 protocol=json.loads((D/'protocol.json').read_text());assert file_hash(args.jobs)==protocol['jobs_sha256']
 keys=[args.key] if args.key else protocol['models']
 for key in keys:
  out=R/key;out.mkdir(parents=True,exist_ok=True);receipt=out/'receipt.json'
  if receipt.exists():raise RuntimeError('Immutable existing run: '+str(out))
  t=time.monotonic()
  while True:
   p=D/(key+'-model.json')
   if p.exists():
    data=json.loads(p.read_text())
    if data['status']=='complete':break
    if data['status']=='failed':raise RuntimeError('Download failed: '+key)
   if time.monotonic()-t>1800:raise TimeoutError('Download not ready: '+key)
   time.sleep(2)
  rec={'model':key,'status':'running','start_utc':now(),'driver_sha256':file_hash(__file__),'protocol_sha256':file_hash(D/'protocol.json'),'jobs_sha256':file_hash(args.jobs),'updates':0};write_json(receipt,rec);start=time.monotonic()
  try:run_worker([sys.executable,str(Path(__file__).resolve()),'--worker',key,'--out',str(out),'--jobs',args.jobs],out/'generate.log',3600);rec['status']='complete'
  except BaseException as e:rec['status']='failed';rec['error']=repr(e)
  finally:rec['elapsed_seconds']=time.monotonic()-start;rec['end_utc']=now();write_json(receipt,rec);print(json.dumps(rec),flush=True)
if __name__=='__main__':main()
