"""Full-weight vLLM actor, immutable output; no labels loaded."""
import argparse,json,os,time
from pathlib import Path
os.environ.setdefault('HF_HUB_OFFLINE','1');os.environ.setdefault('TOKENIZERS_PARALLELISM','false');os.environ.setdefault('VLLM_USE_FLASHINFER_SAMPLER','0')
from prepare import HERE,write,sha
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--jobs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--cap',type=int,default=1024);ap.add_argument('--only',nargs='+');ap.add_argument('--model',type=Path);ap.add_argument('--verify',type=Path);a=ap.parse_args()
 assert a.cap in (1024,2048)
 jobs=json.loads(a.jobs.read_text());jobs=[j for j in jobs if not a.only or j['id'] in a.only];assert jobs and all(not set(j)&{'answer','answer_exact','target','reference'} for j in jobs)
 if a.only:assert set(a.only)=={j['id'] for j in jobs}
 meta=json.loads((HERE/'model.json').read_text());model=str(a.model or meta['snapshot']);a.out.mkdir(exist_ok=False)
 r=dict(status='running',start_unix=time.time(),model=model,revision=meta['revision'],cap=a.cap,samples=8,temperature=1,top_p=1,top_k=-1,completed_groups=0,jobs_sha256=sha(a.jobs),source_sha256=sha(__file__));start=time.monotonic();write(a.out/'receipt.json',r)
 try:
  from transformers import AutoTokenizer
  from vllm import LLM,SamplingParams
  tok=AutoTokenizer.from_pretrained(model,local_files_only=True);tick=time.monotonic()
  engine=LLM(model=model,dtype='bfloat16',max_model_len=4096,max_num_seqs=8,max_num_batched_tokens=2048,gpu_memory_utilization=.82,enforce_eager=True,enable_prefix_caching=False,logprobs_mode='raw_logprobs',seed=2026093000)
  r['loading_seconds']=time.monotonic()-tick
  if a.verify:
   checks=[]
   for v in json.loads(a.verify.read_text()):
    res=engine.generate([{'prompt_token_ids':v['input_ids']}],SamplingParams(max_tokens=1,prompt_logprobs=0,temperature=1,seed=2026093000),use_tqdm=False)[0]
    checks.append(dict(id=v['id'],actor_logps=[float(res.prompt_logprobs[i][v['input_ids'][i]].logprob) for i in range(v['prompt_tokens'],len(v['input_ids']))]))
   write(a.out/'actor-verification.json',checks)
  for j in jobs:
   prompt=tok.apply_chat_template(j['messages'],tokenize=False,add_generation_prompt=True);ids=tok.encode(prompt,add_special_tokens=False);assert len(ids)<=2048 and len(ids)+a.cap<=4096
   tick=time.monotonic();res=engine.generate([{'prompt_token_ids':ids}],SamplingParams(n=8,max_tokens=a.cap,temperature=1,top_p=1,top_k=-1,logprobs=0,seed=j['seed']+a.cap),use_tqdm=False)[0];dt=time.monotonic()-tick
   assert list(res.prompt_token_ids)==ids and len(res.outputs)==8
   records=[]
   for s,c in enumerate(res.outputs):
    cids=list(c.token_ids);records.append(dict(**j,sample=s,prompt_ids=ids,completion_ids=cids,raw_text=tok.decode(cids,skip_special_tokens=False),finish_reason=c.finish_reason,stop_reason=c.stop_reason,rollout_logps=[float(p[t].logprob) for p,t in zip(c.logprobs,cids,strict=True)],cap=a.cap,generation_seconds_group=dt))
   write(a.out/(j['id']+'.json'),records);r['completed_groups']+=1;write(a.out/'receipt.json',r);print(json.dumps(dict(id=j['id'],seconds=dt,lengths=[len(x['completion_ids']) for x in records],finish=[x['finish_reason'] for x in records])),flush=True)
  r['status']='complete'
 except BaseException as e:r.update(status='failed',error=repr(e));raise
 finally:r.update(elapsed_seconds=time.monotonic()-start,end_unix=time.time());write(a.out/'receipt.json',r);print(json.dumps(r),flush=True)
if __name__=='__main__':main()
