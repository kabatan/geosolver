"""Require vLLM effects for both mapped adapters, without scoring answers."""
import os
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('VLLM_USE_FLASHINFER_SAMPLER','0')
import json
from pathlib import Path
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

D=Path(__file__).resolve().parent
ROOT=D.parents[2]
R=ROOT/'qwen/.runtime/research_direction_audit_20260925'
meta=json.loads((ROOT/'docs/research/qwen35-self-materials-2026-09-23/model.json').read_text())
def main():
    tok=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True)
    llm=LLM(model=meta['snapshot'],dtype='bfloat16',max_model_len=4096,max_num_seqs=1,
            max_num_batched_tokens=1024,gpu_memory_utilization=.8,enforce_eager=True,
            language_model_only=True,enable_lora=True,max_lora_rank=32,max_loras=3,
            enable_prefix_caching=False,seed=2026092427)
    jobs=json.loads((D/'bridge-pilot-jobs.json').read_text())
    train=json.loads(Path(json.loads((D/'bridge-train-treatment.json').read_text())['dataset']).read_text())
    prompts={'train-H01':next(r['prompt'] for r in train if r['source']=='H01'),
             'target-H14':jobs[0]['messages'][0]['content']}
    requests={'raw-treatment':LoRARequest('raw',1,str(R/'train-treatment/adapter')),
              'mapped-treatment':LoRARequest('treatment',2,str(R/'train-treatment/adapter-vllm')),
              'mapped-control':LoRARequest('control',3,str(R/'train-control/adapter-vllm'))}
    rows=[]
    for name, prompt in prompts.items():
        rendered=tok.apply_chat_template([{'role':'user','content':prompt}],tokenize=False,
                                         add_generation_prompt=True,enable_thinking=False)
        ids=tok.encode(rendered,add_special_tokens=False)
        params=SamplingParams(temperature=0,max_tokens=1,logprobs=20)
        base=llm.generate([{'prompt_token_ids':ids}],params)[0].outputs[0]
        bp={int(k):float(v.logprob) for k,v in base.logprobs[0].items()}
        for label,request in requests.items():
            out=llm.generate([{'prompt_token_ids':ids}],params,lora_request=request)[0].outputs[0]
            op={int(k):float(v.logprob) for k,v in out.logprobs[0].items()}
            common=set(bp)&set(op)
            delta=max(abs(bp[k]-op[k]) for k in common)
            rows.append({'prompt':name,'adapter':label,'max_abs_common_logprob_difference':delta,
                         'base_token':base.token_ids[0],'adapter_token':out.token_ids[0],
                         'shared_tokens':len(common)})
            if label.startswith('mapped'):
                assert delta>1e-5,(name,label,delta)
    (D/'BRIDGE_ADAPTER_EFFECT.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(rows),flush=True)

if __name__ == "__main__":
    main()
