"""Batched matched foundation comparisons; long generations remain at two sequences."""
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
 if args.non_thinking:assert args.key in ['qwen3_4b','qwen35_9b'] and not args.adapter
 tokenizer_path=meta.get('tokenizer_override',meta['snapshot'])
 tok=AutoTokenizer.from_pretrained(tokenizer_path,local_files_only=True)
 kwargs=dict(model=meta['snapshot'],tokenizer=tokenizer_path,dtype='bfloat16',kv_cache_dtype='auto',max_model_len=args.context,max_num_seqs=8 if args.cap<=8192 else 2,max_num_batched_tokens=1024,gpu_memory_utilization=.85,enforce_eager=True,enable_prefix_caching=False,seed=protocol['seed'])
 if args.key.startswith('qwen35'):kwargs['language_model_only']=True
 if args.adapter:kwargs.update(enable_lora=True,max_lora_rank=32)
 llm=LLM(**kwargs);lora=None
 if args.adapter:
  from vllm.lora.request import LoRARequest
  lora=LoRARequest('foundation',1,args.adapter)
 spec=dict(temperature=.7,top_p=.8,top_k=20) if args.non_thinking and args.key=='qwen3_4b' else protocol['sampling'][args.key]
 rows=json.loads(Path(args.jobs).read_text());prompts=[];params=[];metadata=[]
 for row in rows:
  prompt=tok.apply_chat_template([{'role':'user','content':row['problem']}],tokenize=False,add_generation_prompt=True,enable_thinking=not args.non_thinking)
  ids=tok.encode(prompt,add_special_tokens=False);assert len(ids)+args.cap<=args.context
  seed=stable_seed(protocol['seed'],{'id':row['id'],'problem':row['problem']})%(2**31)
  prompts.append({'prompt_token_ids':ids});params.append(SamplingParams(n=args.samples,**spec,max_tokens=args.cap,seed=seed));metadata.append((prompt,ids,seed))
 tick=time.monotonic();results=llm.generate(prompts,params,lora_request=lora);elapsed=time.monotonic()-tick
 assert len(results)==len(rows)
 for i,(row,result,(prompt,ids,seed)) in enumerate(zip(rows,results,metadata)):
  assert list(result.prompt_token_ids)==ids, 'Mismatched request/output order'
  assert len(result.outputs)==args.samples
  records=[]
  for sample,c in enumerate(result.outputs):
   raw=tok.decode(c.token_ids,skip_special_tokens=False)
   if '</think>' in raw:final=raw.split('</think>',1)[1];method='after_think'
   elif '<think>' in raw or (not args.non_thinking and '<think>' in prompt):final='';method='no_think_close'
   else:final=raw;method='raw_no_think_tag'
   records.append({k:v for k,v in row.items() if k!='reference'}|dict(model=args.key,revision=meta['revision'],sample=sample,prompt_text=prompt,prompt_ids=ids,completion_ids=list(c.token_ids),raw_text=raw,final_text=final,extraction_method=method,tokens=len(c.token_ids),finish_reason=c.finish_reason,seed=seed,completion_cap=args.cap,sampling=spec,elapsed_batch_seconds=elapsed,adapter=args.adapter,non_thinking=args.non_thinking))
  write_json(Path(args.out)/f'group-{i:02}.json',records)
  print(json.dumps(dict(id=row['id'],tokens=[x['tokens'] for x in records],finish=[x['finish_reason'] for x in records])),flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--key',required=True);ap.add_argument('--jobs',required=True);ap.add_argument('--phase',required=True);ap.add_argument('--cap',type=int,default=8192);ap.add_argument('--context',type=int,default=12288);ap.add_argument('--samples',type=int,default=2);ap.add_argument('--adapter');ap.add_argument('--non-thinking',action='store_true');ap.add_argument('--worker',action='store_true');ap.add_argument('--out');args=ap.parse_args()
 if args.worker:return worker(args)
 out=R/(args.phase+'-'+args.key);out.mkdir(parents=True,exist_ok=True);receipt=out/'receipt.json';assert not receipt.exists(),'Immutable run exists'
 rec=dict(status='running',model=args.key,phase=args.phase,start_utc=now(),driver_sha256=file_hash(__file__),model_metadata_sha256=file_hash(D/(args.key+'-model.json')),jobs_sha256=file_hash(args.jobs),protocol_sha256=file_hash(D/'protocol.json'),max_output_tokens=args.cap,max_context=args.context,samples=args.samples,adapter=args.adapter,updates=0,max_num_seqs=8 if args.cap<=8192 else 2,non_thinking=args.non_thinking)
 write_json(receipt,rec);tick=time.monotonic()
 cmd=[sys.executable,str(Path(__file__).resolve()),'--worker','--key',args.key,'--jobs',args.jobs,'--phase',args.phase,'--out',str(out),'--cap',str(args.cap),'--context',str(args.context),'--samples',str(args.samples)]
 if args.adapter:cmd+=['--adapter',args.adapter]
 if args.non_thinking:cmd+=['--non-thinking']
 try:run_worker(cmd,out/'generate.log',2700);rec['status']='complete'
 except BaseException as e:rec.update(status='failed',error=repr(e));raise
 finally:rec.update(elapsed_seconds=time.monotonic()-tick,end_utc=now());write_json(receipt,rec);print(json.dumps(rec),flush=True)

if __name__=='__main__':main()
