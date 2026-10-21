"""Isolated, immutable, sequential-model inference for the foundation pilot."""
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
R=Path('qwen/.runtime/foundation_pilot_20260923')

def worker(args):
 from transformers import AutoTokenizer
 from vllm import LLM,SamplingParams
 meta=json.loads((D/(args.key+'-model.json')).read_text());assert meta['status']=='complete'
 protocol=json.loads((D/'protocol.json').read_text())
 tokenizer=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True)
 kwargs=dict(model=meta['snapshot'],dtype='bfloat16',kv_cache_dtype='auto',max_model_len=args.context,max_num_seqs=2,max_num_batched_tokens=1024,gpu_memory_utilization=.85,enforce_eager=True,enable_prefix_caching=False,seed=protocol['seed'])
 if args.key.startswith('qwen35'):kwargs['language_model_only']=True
 if args.adapter:
  kwargs.update(enable_lora=True,max_lora_rank=32)
 llm=LLM(**kwargs)
 lora=None
 if args.adapter:
  from vllm.lora.request import LoRARequest
  lora=LoRARequest('foundation',1,args.adapter)
 spec=protocol['sampling'][args.key]
 for i,row in enumerate(json.loads(Path(args.jobs).read_text())):
  messages=[{'role':'user','content':row['problem']}]
  prompt=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=True)
  ids=tokenizer.encode(prompt,add_special_tokens=False)
  assert len(ids)+args.cap<=args.context,(row['id'],len(ids),args.cap,args.context)
  seed=stable_seed(protocol['seed'],{'id':row['id'],'problem':row['problem']})%(2**31)
  start=time.monotonic()
  result=llm.generate([{'prompt_token_ids':ids}],SamplingParams(n=args.samples,**spec,max_tokens=args.cap,seed=seed),lora_request=lora)[0]
  seconds=time.monotonic()-start;records=[]
  for sample,c in enumerate(result.outputs):
   raw=tokenizer.decode(c.token_ids,skip_special_tokens=False)
   if '</think>' in raw:final=raw.split('</think>',1)[1];method='after_think'
   elif '<think>' in prompt or '<think>' in raw:final='';method='no_think_close'
   else:final=raw;method='raw_no_think_tag'
   records.append({k:v for k,v in row.items() if k!='reference'} | dict(model=args.key,revision=meta['revision'],sample=sample,prompt_text=prompt,prompt_ids=ids,completion_ids=list(c.token_ids),raw_text=raw,final_text=final,extraction_method=method,tokens=len(c.token_ids),finish_reason=c.finish_reason,seed=seed,completion_cap=args.cap,sampling=spec,elapsed_group_seconds=seconds,adapter=args.adapter))
  write_json(Path(args.out)/f'group-{i:02}.json',records)
  print(json.dumps(dict(model=args.key,id=row['id'],tokens=[r['tokens'] for r in records],finish=[r['finish_reason'] for r in records],seconds=round(seconds,2))),flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--key',required=True);ap.add_argument('--jobs',default=str(D/'screen-jobs.json'));ap.add_argument('--phase',default='screen');ap.add_argument('--cap',type=int,default=8192);ap.add_argument('--context',type=int,default=12288);ap.add_argument('--samples',type=int,default=2);ap.add_argument('--adapter');ap.add_argument('--worker',action='store_true');ap.add_argument('--out');args=ap.parse_args()
 if args.worker:return worker(args)
 out=R/(args.phase+'-'+args.key);out.mkdir(parents=True,exist_ok=True)
 receipt=out/'receipt.json';assert not receipt.exists(),'Immutable run exists: '+str(out)
 rec=dict(model=args.key,phase=args.phase,status='running',start_utc=now(),driver_sha256=file_hash(__file__),jobs_sha256=file_hash(args.jobs),protocol_sha256=file_hash(D/'protocol.json'),max_output_tokens=args.cap,max_context=args.context,samples=args.samples,adapter=args.adapter,updates=0)
 write_json(receipt,rec);start=time.monotonic()
 cmd=[sys.executable,str(Path(__file__).resolve()),'--worker','--key',args.key,'--jobs',args.jobs,'--phase',args.phase,'--out',str(out),'--cap',str(args.cap),'--context',str(args.context),'--samples',str(args.samples)]
 if args.adapter:cmd+=['--adapter',args.adapter]
 try:run_worker(cmd,out/'generate.log',2700);rec['status']='complete'
 except BaseException as e:rec.update(status='failed',error=repr(e));raise
 finally:
  rec.update(elapsed_seconds=time.monotonic()-start,end_utc=now());write_json(receipt,rec);print(json.dumps(rec),flush=True)
if __name__=='__main__':main()
