"""Immutable probability-recording rollout/actor-reload worker; no answer keys."""
import argparse,hashlib,json,os,time
from pathlib import Path
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('VLLM_USE_FLASHINFER_SAMPLER','0')
os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
META=ROOT/'docs/research/qwen35-self-materials-2026-09-23/model.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
    p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n');tmp.replace(p)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--jobs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--cap',type=int,default=16384);ap.add_argument('--adapter',type=Path);ap.add_argument('--only',nargs='+');ap.add_argument('--verify',type=Path);a=ap.parse_args()
    if a.cap not in (16384,32768):raise ValueError('unregistered cap')
    jobs=json.loads(a.jobs.read_text());jobs=[j for j in jobs if not a.only or j['id'] in a.only]
    if not jobs or any(set(j)&{'answer','answer_exact','target','reference'} for j in jobs):raise ValueError('empty jobs or label leakage')
    if a.only and {j['id'] for j in jobs}!=set(a.only):raise ValueError('unknown subset')
    meta=json.loads(META.read_text());out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='running',start_unix=time.time(),jobs_sha256=sha(a.jobs),driver_sha256=sha(__file__),model_revision=meta['revision'],adapter_sha256=sha(a.adapter/'adapter_model.safetensors') if a.adapter else None,cap=a.cap,context=40960,samples=4,temperature=1,top_p=1,top_k=-1,presence_penalty=0,enable_thinking=False,completed_groups=0)
    write(out/'receipt.json',receipt);started=time.monotonic()
    try:
        from transformers import AutoTokenizer
        from vllm import LLM,SamplingParams
        from vllm.lora.request import LoRARequest
        tok=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True)
        tick=time.monotonic()
        engine=LLM(model=meta['snapshot'],dtype='bfloat16',kv_cache_dtype='auto',max_model_len=40960,max_num_seqs=4,max_num_batched_tokens=1024,gpu_memory_utilization=0.82,enforce_eager=True,enable_prefix_caching=False,language_model_only=True,enable_lora=True,max_lora_rank=8,max_loras=1,lora_dtype='bfloat16',logprobs_mode='raw_logprobs',seed=2026093040)
        receipt['loading_seconds']=time.monotonic()-tick
        lora=LoRARequest('rl_probe',1,str(a.adapter.resolve())) if a.adapter else None
        if a.verify:
            verification=json.loads(a.verify.read_text());checks=[]
            for v in verification:
                tick=time.monotonic();res=engine.generate([{'prompt_token_ids':v['input_ids']}],SamplingParams(max_tokens=1,temperature=1,top_p=1,top_k=-1,prompt_logprobs=0,seed=2026093040),lora_request=lora,use_tqdm=False)[0]
                logs=[]
                for pos in range(v['prompt_tokens'],len(v['input_ids'])):
                    token=v['input_ids'][pos];logs.append(float(res.prompt_logprobs[pos][token].logprob))
                checks.append(dict(id=v['id'],actor_logps=logs,learner_before_logps=v['before_logps'],learner_after_logps=v['after_logps'],seconds=time.monotonic()-tick))
            write(out/'actor-verification.json',checks);receipt['verification_sha256']=sha(a.verify)
        for j in jobs:
            prompt=tok.apply_chat_template(j['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=False)
            pids=tok.encode(prompt,add_special_tokens=False)
            if len(pids)+a.cap>40960:raise ValueError('context bound')
            tick=time.monotonic();res=engine.generate([{'prompt_token_ids':pids}],SamplingParams(n=4,max_tokens=a.cap,temperature=1,top_p=1,top_k=-1,logprobs=0,seed=j['seed']),lora_request=lora,use_tqdm=False)[0];elapsed=time.monotonic()-tick
            if list(res.prompt_token_ids)!=pids or len(res.outputs)!=4:raise ValueError('generation identity')
            records=[]
            for sample,c in enumerate(res.outputs):
                ids=list(c.token_ids);raw=tok.decode(ids,skip_special_tokens=False)
                logs=[float(p[t].logprob) for p,t in zip(c.logprobs,ids,strict=True)]
                records.append(dict(**j,sample=sample,prompt_ids=pids,completion_ids=ids,raw_text=raw,finish_reason=c.finish_reason,stop_reason=c.stop_reason,rollout_logps=logs,policy_adapter_sha256=receipt['adapter_sha256'],model_revision=meta['revision'],cap=a.cap,generation_seconds_group=elapsed))
            write(out/(j['id']+'.json'),records);receipt['completed_groups']+=1;write(out/'receipt.json',receipt)
            print(json.dumps(dict(id=j['id'],lengths=[len(r['completion_ids']) for r in records],finish=[r['finish_reason'] for r in records],seconds=elapsed)),flush=True)
        receipt['status']='complete'
    except BaseException as e:receipt.update(status='failed',error=repr(e));raise
    finally:
        receipt.update(end_unix=time.time(),elapsed_seconds=time.monotonic()-started);write(out/'receipt.json',receipt)
        print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
