"""Disposable local LoRA mechanics check; never used for mathematical evaluation."""
import os
os.environ.setdefault('HF_HUB_OFFLINE','1');os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
import argparse,json,time,gc,hashlib,importlib.metadata
from pathlib import Path
import torch
from transformers import AutoTokenizer,AutoModelForCausalLM,AutoModelForImageTextToText
from peft import LoraConfig,get_peft_model,TaskType
D=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('key');ap.add_argument('--length',type=int,default=2048);args=ap.parse_args()
meta=json.loads((D/(args.key+'-model.json')).read_text());assert meta['status']=='complete'
out=Path('qwen/.runtime/model_search_20260923')/(args.key+f'-smoke-{args.length}');out.mkdir(parents=True,exist_ok=True)
receipt=out/'receipt.json';assert not receipt.exists();t0=time.monotonic()
rec={'status':'running','model':args.key,'revision':meta['revision'],'sequence_length':args.length,'dtype':'bfloat16','updates':0,'research_training':False,'training_text':'Repeated generic arithmetic smoke-test sentence; no research problems or target relations','target_tokens':256}
rec.update(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), torch=torch.__version__, transformers=importlib.metadata.version('transformers'), peft=importlib.metadata.version('peft'), cuda=torch.version.cuda, gpu=torch.cuda.get_device_name())
receipt.write_text(json.dumps(rec,indent=2)+'\n')
try:
 torch.manual_seed(20260923)
 tokenizer=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True)
 cls=AutoModelForImageTextToText if args.key.startswith('qwen35') else AutoModelForCausalLM
 model=cls.from_pretrained(meta['snapshot'],dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa',local_files_only=True)
 targets=[n for n,m in model.named_modules() if isinstance(m,torch.nn.Linear) and 'visual' not in n and 'vision' not in n and not n.endswith('lm_head')]
 assert targets
 model=get_peft_model(model,LoraConfig(r=32,lora_alpha=64,lora_dropout=0.,target_modules=targets,bias='none',task_type=TaskType.CAUSAL_LM))
 model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.enable_input_require_grads();model.train()
 tokens=tokenizer.encode('This is a technical training check. Seventeen plus twenty-five equals forty-two. ',add_special_tokens=False)
 ids=torch.tensor((tokens*((args.length+len(tokens)-1)//len(tokens)))[:args.length],device='cuda').unsqueeze(0)
 opt=torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),lr=1e-4)
 before={n:p.detach().float().cpu().clone() for n,p in model.named_parameters() if p.requires_grad}
 rec['trainable_parameters']=sum(p.numel() for p in model.parameters() if p.requires_grad);rec['lora_target_modules']=targets
 torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();t=time.monotonic()
 outputs=model(input_ids=ids,use_cache=False,logits_to_keep=257)
 logits=outputs.logits[:,-257:-1,:].float()
 loss=torch.nn.functional.cross_entropy(logits.reshape(-1,logits.shape[-1]),ids[:,-256:].reshape(-1));assert torch.isfinite(loss)
 loss.backward();assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
 opt.step();opt.zero_grad(set_to_none=True);torch.cuda.synchronize()
 rec.update(updates=1,step_seconds=time.monotonic()-t,loss=float(loss.detach()),peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30)
 rec['changed_tensors']=sum(not torch.equal(before[n],p.detach().float().cpu()) for n,p in model.named_parameters() if n in before);assert rec['changed_tensors']>0
 del outputs,logits,loss,before,opt;gc.collect();torch.cuda.empty_cache()
 model.eval()
 with torch.no_grad():expected=model(input_ids=ids[:,:64],use_cache=False,logits_to_keep=1).logits[:,-1,:].float().cpu()
 model.save_pretrained(out/'adapter')
 model.delete_adapter('default');model.load_adapter(out/'adapter',adapter_name='reloaded',is_trainable=False);model.set_adapter('reloaded');model.eval()
 with torch.no_grad():actual=model(input_ids=ids[:,:64],use_cache=False,logits_to_keep=1).logits[:,-1,:].float().cpu()
 rec['reload_max_abs_logit_difference']=float((expected-actual).abs().max());assert torch.allclose(expected,actual,atol=1e-4,rtol=1e-4)
 rec['status']='complete'
except BaseException as e:
 rec['status']='failed';rec['error']=repr(e);raise
finally:
 rec['elapsed_seconds']=time.monotonic()-t0;receipt.write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps({k:v for k,v in rec.items() if k!='lora_target_modules'}),flush=True)
