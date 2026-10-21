"""Verify updated LoRA with base/updated log-probs in the same vLLM engine."""
import argparse,json,time
from pathlib import Path
import rollout

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--jobs',type=Path,required=True);ap.add_argument('--only',required=True);ap.add_argument('--adapter',type=Path,required=True);ap.add_argument('--verify',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--cap',type=int,required=True);a=ap.parse_args()
    from transformers import AutoTokenizer
    from vllm import LLM,SamplingParams
    from vllm.lora.request import LoRARequest
    jobs=json.loads(a.jobs.read_text());j=next(j for j in jobs if j['id']==a.only)
    if set(j)&{'answer','target','reference'} or a.cap not in (16384,32768):raise ValueError('invalid generation input')
    meta=json.loads(rollout.META.read_text());out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    receipt=dict(status='running',start_unix=time.time(),driver_sha256=rollout.sha(__file__),jobs_sha256=rollout.sha(a.jobs),verification_sha256=rollout.sha(a.verify),adapter_sha256=rollout.sha(a.adapter/'adapter_model.safetensors'),model_revision=meta['revision'],cap=a.cap,samples=4,temperature=1,top_p=1,top_k=-1,enable_thinking=False,scope='technical same-problem actor reload; not transfer or training efficacy')
    rollout.write(out/'receipt.json',receipt)
    try:
        tok=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True);tick=time.monotonic()
        engine=LLM(model=meta['snapshot'],dtype='bfloat16',kv_cache_dtype='auto',max_model_len=40960,max_num_seqs=4,max_num_batched_tokens=1024,gpu_memory_utilization=0.82,enforce_eager=True,enable_prefix_caching=False,language_model_only=True,enable_lora=True,max_lora_rank=8,max_loras=1,lora_dtype='bfloat16',logprobs_mode='raw_logprobs',seed=2026093040)
        receipt['loading_seconds']=time.monotonic()-tick;lora=LoRARequest('rl_probe',1,str(a.adapter.resolve()));checks=[]
        for v in json.loads(a.verify.read_text()):
            tick=time.monotonic();both=[]
            for adapter in (None,lora):
                r=engine.generate([{'prompt_token_ids':v['input_ids']}],SamplingParams(max_tokens=1,temperature=1,top_p=1,top_k=-1,prompt_logprobs=0,seed=2026093040),lora_request=adapter,use_tqdm=False)[0]
                both.append([float(r.prompt_logprobs[k][v['input_ids'][k]].logprob) for k in range(v['prompt_tokens'],len(v['input_ids']))])
            checks.append(dict(id=v['id'],actor_before_logps=both[0],actor_after_logps=both[1],learner_before_logps=v['before_logps'],learner_after_logps=v['after_logps'],seconds=time.monotonic()-tick))
        rollout.write(out/'actor-verification.json',checks);receipt['fixed_verification_seconds']=sum(c['seconds'] for c in checks)
        prompt=tok.apply_chat_template(j['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=False);pids=tok.encode(prompt,add_special_tokens=False)
        tick=time.monotonic();res=engine.generate([{'prompt_token_ids':pids}],SamplingParams(n=4,max_tokens=a.cap,temperature=1,top_p=1,top_k=-1,logprobs=0,seed=j['seed']),lora_request=lora,use_tqdm=False)[0];elapsed=time.monotonic()-tick
        if list(res.prompt_token_ids)!=pids or len(res.outputs)!=4:raise ValueError('generation identity')
        rows=[]
        for sample,c in enumerate(res.outputs):
            ids=list(c.token_ids);logs=[float(p[t].logprob) for p,t in zip(c.logprobs,ids,strict=True)]
            rows.append(dict(**j,sample=sample,prompt_ids=pids,completion_ids=ids,raw_text=tok.decode(ids,skip_special_tokens=False),finish_reason=c.finish_reason,stop_reason=c.stop_reason,rollout_logps=logs,policy_adapter_sha256=receipt['adapter_sha256'],model_revision=meta['revision'],cap=a.cap,generation_seconds_group=elapsed))
        rollout.write(out/(j['id']+'.json'),rows);receipt.update(generation_seconds=elapsed,status='complete')
    except BaseException as e:receipt.update(status='failed',error=repr(e));raise
    finally:
        receipt.update(end_unix=time.time(),elapsed_seconds=time.monotonic()-start);rollout.write(out/'receipt.json',receipt);print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
