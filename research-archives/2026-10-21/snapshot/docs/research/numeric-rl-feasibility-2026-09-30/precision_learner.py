"""FP16 teacher-forcing on the same saved weights, no generation or update."""
import argparse,json,time
from pathlib import Path
from signal_analysis import sha,write
from train_probe import hidden
from qwen.grpo_loss import frozen_head_logps
import torch

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--base-meta',type=Path,required=True);ap.add_argument('--adapter',type=Path,required=True);ap.add_argument('--zero-adapter',type=Path,required=True);ap.add_argument('--verify',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 out=a.out;out.mkdir(exist_ok=False);start=time.monotonic();r=dict(status='running',dtype='float16',scope='Fixed-prefix same-checkpoint diagnostic; zero updates and no generation',actual_updates=0,source_sha256=sha(__file__),adapter_sha256=sha(a.adapter/'adapter_model.safetensors'),zero_sha256=sha(a.zero_adapter/'adapter_model.safetensors'),verification_sha256=sha(a.verify));write(out/'receipt.json',r)
 try:
  from peft import PeftModel
  from transformers import AutoModelForCausalLM
  torch.set_num_threads(4);meta=json.loads(a.base_meta.read_text());tick=time.monotonic();base=AutoModelForCausalLM.from_pretrained(meta['snapshot'],dtype=torch.float16,device_map='cuda',attn_implementation='sdpa',local_files_only=True)
  model=PeftModel.from_pretrained(base,a.zero_adapter,adapter_name='zero');model.load_adapter(a.adapter,adapter_name='updated');model.eval();r['loading_seconds']=time.monotonic()-tick;r['lora_dtypes']=sorted({str(p.dtype) for n,p in model.named_parameters() if 'lora_' in n});checks=[]
  for v in json.loads(a.verify.read_text()):
   row=dict(prompt_ids=v['input_ids'][:v['prompt_tokens']],completion_ids=v['input_ids'][v['prompt_tokens']:]);both=[]
   for name in ('zero','updated'):
    model.set_adapter(name);model.eval()
    with torch.no_grad():
     h,t=hidden(model,row);lp=frozen_head_logps(h,model.get_base_model().lm_head.weight,t,temperature=1,chunk_size=64).flatten().cpu().tolist();both.append(lp)
   checks.append(dict(id=v['id'],before_logps=both[0],after_logps=both[1]))
  write(out/'verification.json',checks);r['status']='complete'
 except BaseException as e:r.update(status='failed',error=repr(e));raise
 finally:r['elapsed_seconds']=time.monotonic()-start;write(out/'receipt.json',r);print(json.dumps(r),flush=True)
if __name__=='__main__':main()
