import os
os.environ['HF_HUB_OFFLINE']='1'
import json,torch
from pathlib import Path
from transformers import AutoModelForCausalLM,AutoTokenizer
from peft import PeftModel
from safetensors.torch import load_file
D=Path(__file__).resolve().parent;R=Path('qwen/.runtime/foundation_pilot_20260923/sft-qwen3_4b')
m=json.loads((D/'qwen3_4b-model.json').read_text());t=AutoTokenizer.from_pretrained(m['snapshot'])
row=json.loads((D/'foundation-train-v2.json').read_text())[0]
prompt=t.apply_chat_template([{'role':'user','content':row['problem']+'\nGive a complete, concise mathematical justification.'}],tokenize=False,add_generation_prompt=True,enable_thinking=True)
ids=torch.tensor([t.encode(prompt,add_special_tokens=False)],device='cuda')
b=AutoModelForCausalLM.from_pretrained(m['snapshot'],dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa')
p=PeftModel.from_pretrained(b,R/'adapter',is_trainable=False);p.eval()
a={n:v.detach().cpu().clone() for n,v in p.named_parameters() if 'lora_' in n}
with torch.no_grad():x=p(input_ids=ids,use_cache=False,logits_to_keep=1).logits.float().cpu()
p.delete_adapter('default');p.load_adapter(R/'adapter',adapter_name='reloaded',is_trainable=False);p.set_adapter('reloaded');p.eval()
c={n.replace('.reloaded.','.default.'):v.detach().cpu().clone() for n,v in p.named_parameters() if 'lora_' in n}
with torch.no_grad():y=p(input_ids=ids,use_cache=False,logits_to_keep=1).logits.float().cpu()
print('FIRST DTYPE',next(iter(a.values())).dtype,'SECOND',next(iter(c.values())).dtype,flush=True)
print('PARAMS',len(a),len(c),'UNEQUAL',sum(not torch.equal(a[n],c[n]) for n in a),'MAX',max(float((a[n].float()-c[n].float()).abs().max()) for n in a),flush=True)
print('LOGITS',float((x-y).abs().max()),'active',p.active_adapters,flush=True)
for n,v in p.named_parameters():
 if 'lora_' in n:v.data=v.data.float()
with torch.no_grad():z=p(input_ids=ids,use_cache=False,logits_to_keep=1).logits.float().cpu()
print('FORCED_FLOAT_DIFF',float((x-z).abs().max()),flush=True)
print('DISK',next(iter(load_file(R/'adapter/adapter_model.safetensors').values())).dtype,flush=True)
