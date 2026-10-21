"""Diagnose catastrophic short-answer FT without changing its curriculum/recipe."""
import os
os.environ['HF_HUB_OFFLINE']='1';os.environ['TOKENIZERS_PARALLELISM']='false'
os.environ.setdefault('VLLM_USE_FLASHINFER_SAMPLER','0')
import argparse,json,subprocess,sys,time
from pathlib import Path
from qwen.common import now,write_json,file_hash
D=Path(__file__).resolve().parent;R=Path('qwen/.runtime/foundation_pilot_20260923');OUT=R/os.environ.get('FT_FIDELITY_DIR','ft-fidelity')

def jobs():
 t=json.loads((D/'foundation-train-v2.json').read_text());c=json.loads((D/'confirmation-jobs.json').read_text())
 return [dict(id=x['id'],problem=x['problem']+'\nGive a complete, concise mathematical justification.',kind='train') for x in t if x['id'] in ['T04-v0','T09-v0','T20-v0']]+[dict(id=x['id'],problem=x['problem'],kind='heldout') for x in c if x['id'] in ['C03','C04','C16']]

def worker(backend):
 from transformers import AutoTokenizer
 meta=json.loads((D/'qwen3_4b-model.json').read_text());tok=AutoTokenizer.from_pretrained(meta['snapshot']);adapter=R/'sft-qwen3_4b-replay/adapter'
 rows=jobs();prompts=[tok.encode(tok.apply_chat_template([{'role':'user','content':x['problem']}],tokenize=False,add_generation_prompt=True,enable_thinking=True),add_special_tokens=False) for x in rows]
 output=[]
 if backend=='hf':
  import torch
  from transformers import AutoModelForCausalLM
  from peft import PeftModel
  m=AutoModelForCausalLM.from_pretrained(meta['snapshot'],dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa');m=PeftModel.from_pretrained(m,adapter);m.eval()
  for mode in ['fp32_lora','bf16_lora']:
   if mode=='bf16_lora':
    for n,p in m.named_parameters():
     if 'lora_' in n:p.data=p.data.bfloat16()
   for row,prompt in zip(rows,prompts):
    ids=torch.tensor([prompt],device='cuda')
    with torch.no_grad():
     pred=m(input_ids=ids,use_cache=False,logits_to_keep=1).logits[0,-1].float().log_softmax(-1)
     top=pred.topk(20)
     gen=m.generate(input_ids=ids,attention_mask=torch.ones_like(ids),do_sample=False,max_new_tokens=512,pad_token_id=tok.eos_token_id)
    completion=gen[0,len(prompt):].tolist()
    output.append(row|dict(mode=mode,ids=completion,raw=tok.decode(completion,skip_special_tokens=False),first_top20={str(i):v for i,v in zip(top.indices.tolist(),top.values.tolist())}))
 else:
  from vllm import LLM,SamplingParams
  from vllm.lora.request import LoRARequest
  m=LLM(model=meta['snapshot'],dtype='bfloat16',kv_cache_dtype='auto',max_model_len=12288,max_num_seqs=8,max_num_batched_tokens=1024,gpu_memory_utilization=.85,enforce_eager=True,enable_prefix_caching=False,enable_lora=True,max_lora_rank=32)
  gen=m.generate([{'prompt_token_ids':p} for p in prompts],SamplingParams(temperature=0,top_p=1,top_k=-1,max_tokens=512,logprobs=20),lora_request=LoRARequest('foundation',1,str(adapter.resolve())))
  for row,g in zip(rows,gen):
   c=g.outputs[0];output.append(row|dict(mode='vllm_bf16',ids=list(c.token_ids),raw=tok.decode(c.token_ids,skip_special_tokens=False),first_top20={str(i):v.logprob for i,v in c.logprobs[0].items()}))
 write_json(OUT/(backend+'.json'),output)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--worker',choices=['hf','vllm']);a=ap.parse_args()
 if a.worker:worker(a.worker)
 else:
  while True:
   p=R/'direct-target-qwen35_9b/receipt.json'
   if p.exists() and json.loads(p.read_text())['status']=='complete':break
   time.sleep(10)
  OUT.mkdir();r=dict(status='running',start_utc=now(),purpose='Training-versus-serving fidelity diagnostic; not an additional FT recipe or model selection trial',script_sha256=file_hash(__file__));write_json(OUT/'receipt.json',r);t=time.monotonic()
  try:
   for backend in ['hf','vllm']:
    with (OUT/(backend+'.log')).open('w') as log:subprocess.run([sys.executable,__file__,'--worker',backend],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
   r['status']='complete'
  except BaseException as e:r.update(status='failed',error=repr(e));raise
  finally:r.update(elapsed_seconds=time.monotonic()-t,end_utc=now());write_json(OUT/'receipt.json',r)
