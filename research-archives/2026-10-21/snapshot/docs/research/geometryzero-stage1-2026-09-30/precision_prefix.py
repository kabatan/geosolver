"""Read-only fixed-prefix FP16 learner diagnostic; no optimizer or generation."""
import gc,json,time
from prepare import HERE,RUN,write
from full_update import logps
import torch
def main():
 from transformers import AutoModelForCausalLM
 torch.set_num_threads(4);meta=json.loads((HERE/'model.json').read_text());out={};start=time.monotonic()
 for name,path in [('base',meta['snapshot']),('DA08',str(RUN/'update-DA08/model')),('DA06',str(RUN/'update-DA06/model'))]:
  model=AutoModelForCausalLM.from_pretrained(path,dtype=torch.float16,device_map='cuda',attn_implementation='sdpa',local_files_only=True);model.eval();checks=[];probes=json.loads((RUN/'base-actor-probes.json').read_text()) if name=='base' else json.loads((RUN/('update-'+name)/'fixed-probes.json').read_text())
  for v in probes:
   row=dict(prompt_ids=v['input_ids'][:v['prompt_tokens']],completion_ids=v['input_ids'][v['prompt_tokens']:])
   with torch.no_grad():lp=logps(model,row).cpu().tolist()
   checks.append(dict(id=v['id'],learner_logps=lp))
  out[name]=checks;write(RUN/'fp16-learner-prefixes.json',out);del model;gc.collect();torch.cuda.empty_cache()
 write(RUN/'fp16-learner-receipt.json',dict(status='complete',actual_updates=0,seconds=time.monotonic()-start,dtype='float16',scope='fixed prefixes only'))
if __name__=='__main__':main()
