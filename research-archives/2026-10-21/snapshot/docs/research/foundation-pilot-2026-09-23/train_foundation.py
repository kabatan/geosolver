"""One fixed, assistant-only BF16 LoRA pilot. No target or eval training."""
import os
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
import argparse,gc,hashlib,importlib.metadata,json,math,random,time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from peft import LoraConfig,TaskType,get_peft_model
from qwen.common import write_json,now,file_hash

D=Path(__file__).resolve().parent
OUT=Path('qwen/.runtime/foundation_pilot_20260923/sft-qwen3_4b')

def main():
 protocol=json.loads((D/'sft-protocol-v2.json').read_text())
 meta=json.loads((D/'qwen3_4b-model.json').read_text())
 train_file=D/protocol['train_file']
 assert file_hash(train_file)==protocol['train_sha256']
 assert file_hash(D/'confirmation-jobs.json')==protocol['confirmation_sha256']
 OUT.mkdir(parents=True,exist_ok=True)
 receipt=OUT/'receipt.json';assert not receipt.exists(),'Immutable training run already exists'
 rec=dict(status='running',start_utc=now(),script_sha256=file_hash(__file__),protocol=protocol,model_revision=meta['revision'],updates=0,
          versions={k:importlib.metadata.version(k) for k in ['torch','transformers','peft']})
 write_json(receipt,rec);start=time.monotonic()
 try:
  torch.manual_seed(protocol['seed']);torch.cuda.manual_seed_all(protocol['seed'])
  tok=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True)
  data=[]
  for row in json.loads(train_file.read_text()):
   user=row['problem']+'\nGive a complete, concise mathematical justification.'
   prompt=tok.apply_chat_template([{'role':'user','content':user}],tokenize=False,add_generation_prompt=True,enable_thinking=True)
   # Original Qwen3 emits the opening think tag itself, unlike Thinking-2507.
   # Use its native full conversation template rather than assuming a prefill.
   content='<think>\n'+row['plan']+'\n</think>\n\n'+row['answer']
   full=tok.apply_chat_template([{'role':'user','content':user},{'role':'assistant','content':content}],tokenize=False,enable_thinking=True)
   assert full.startswith(prompt), 'Training and inference chat boundaries differ'
   answer=full[len(prompt):]
   assert tok.eos_token in answer
   answer=answer[:answer.rindex(tok.eos_token)+len(tok.eos_token)]
   assert answer.startswith('<think>\n') and '</think>\n\n' in answer
   pids=tok.encode(prompt,add_special_tokens=False);aids=tok.encode(answer,add_special_tokens=False)
   assert aids[-1]==tok.eos_token_id and len(pids)>0 and len(aids)>20
   assert len(pids)+len(aids)<=2048, 'Never truncate a teacher proof'
   data.append(dict(id=row['id'],prompt=pids,answer=aids))
  write_json(OUT/'tokenization.json',[dict(id=r['id'],prompt_tokens=len(r['prompt']),answer_tokens=len(r['answer'])) for r in data])
  rec.update(n_examples=len(data),n_unique_structures=24,max_sequence_tokens=max(len(x['prompt'])+len(x['answer']) for x in data),
             answer_tokens_per_epoch=sum(len(x['answer']) for x in data),loss_mask='Only positions predicting authored assistant tokens, including EOS. All user tokens excluded.')
  model=AutoModelForCausalLM.from_pretrained(meta['snapshot'],dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa',local_files_only=True)
  model=get_peft_model(model,LoraConfig(r=protocol['lora_rank'],lora_alpha=protocol['lora_alpha'],lora_dropout=0.,target_modules=protocol['modules'].split(','),bias='none',task_type=TaskType.CAUSAL_LM))
  model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.enable_input_require_grads();model.train()
  trainable=[p for p in model.parameters() if p.requires_grad]
  assert trainable and all('lora_' in n for n,p in model.named_parameters() if p.requires_grad)
  rec['trainable_parameters']=sum(p.numel() for p in trainable)
  before={n:p.detach().float().cpu().clone() for n,p in model.named_parameters() if p.requires_grad}
  opt=torch.optim.AdamW(trainable,lr=protocol['lr'],weight_decay=0.)
  torch.cuda.reset_peak_memory_stats();ttrain=time.monotonic();global_step=0
  for epoch in range(protocol['epochs']):
   order=list(range(len(data)));random.Random(protocol['seed']+epoch).shuffle(order)
   for off in range(0,len(order),protocol['effective_batch']):
    batch=order[off:off+protocol['effective_batch']]
    opt.zero_grad(set_to_none=True);losses=[];tick=time.monotonic()
    global_step+=1
    if global_step<=protocol['warmup_updates']:lr=protocol['lr']*global_step/protocol['warmup_updates']
    else:
     progress=(global_step-protocol['warmup_updates'])/(protocol['updates']-protocol['warmup_updates'])
     lr=protocol['min_lr']+.5*(protocol['lr']-protocol['min_lr'])*(1+math.cos(math.pi*progress))
    for group in opt.param_groups:group['lr']=lr
    for idx in batch:
     row=data[idx];n=len(row['answer'])
     ids=torch.tensor([row['prompt']+row['answer']],device='cuda',dtype=torch.long)
     target=torch.tensor(row['answer'],device='cuda',dtype=torch.long)
     # The first retained logit is at the last prompt token, predicting answer[0].
     output=model(input_ids=ids,use_cache=False,logits_to_keep=n+1)
     logits=output.logits[0,:-1,:].float();assert logits.shape[0]==n
     loss=torch.nn.functional.cross_entropy(logits,target)
     assert torch.isfinite(loss)
     (loss/len(batch)).backward();losses.append(float(loss.detach()))
     del output,logits,loss,ids,target
    norm=torch.nn.utils.clip_grad_norm_(trainable,protocol['grad_clip']);assert torch.isfinite(norm)
    assert all(p.grad is None for p in model.parameters() if not p.requires_grad)
    opt.step();torch.cuda.synchronize()
    event=dict(update=global_step,epoch=epoch,lr=lr,mean_loss=sum(losses)/len(losses),grad_norm=float(norm),seconds=time.monotonic()-tick,ids=[data[i]['id'] for i in batch])
    with (OUT/'updates.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
    print(json.dumps(event),flush=True)
    rec['updates']=global_step
  assert global_step==protocol['updates']
  rec.update(training_seconds=time.monotonic()-ttrain,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30)
  rec['changed_tensors']=sum(not torch.equal(before[n],p.detach().float().cpu()) for n,p in model.named_parameters() if n in before);assert rec['changed_tensors']>0
  del opt,before;gc.collect();torch.cuda.empty_cache();model.eval()
  check_ids=torch.tensor([data[0]['prompt']],device='cuda')
  with torch.no_grad():expected=model(input_ids=check_ids,use_cache=False,logits_to_keep=1).logits[:,-1,:].float().cpu()
  model.save_pretrained(OUT/'adapter');tok.save_pretrained(OUT/'tokenizer')
  # PEFT 0.18 load_adapter creates BF16 modules, copies FP32 weights into
  # them, and only then promotes them. Allocate FP32 before the copy so
  # this round trip tests serialization without an unintended rounding.
  expected_weights={n.replace('.default.','.reloaded.'):p.detach().cpu().clone() for n,p in model.named_parameters() if 'lora_' in n}
  model.delete_adapter('default')
  model.add_adapter('reloaded',LoraConfig.from_pretrained(OUT/'adapter'))
  for n,p in model.named_parameters():
   if '.reloaded.' in n:p.data=p.data.float()
  model.load_adapter(OUT/'adapter',adapter_name='reloaded',is_trainable=False);model.set_adapter('reloaded');model.eval()
  rec['reload_equal_tensors']=sum(torch.equal(expected_weights[n],p.detach().cpu()) for n,p in model.named_parameters() if n in expected_weights)
  assert rec['reload_equal_tensors']==len(expected_weights)
  with torch.no_grad():actual=model(input_ids=check_ids,use_cache=False,logits_to_keep=1).logits[:,-1,:].float().cpu()
  rec['reload_max_abs_logit_difference']=float((expected-actual).abs().max());assert torch.allclose(expected,actual,atol=1e-4,rtol=1e-4)
  rec.update(status='complete',adapter_sha256=file_hash(OUT/'adapter/adapter_model.safetensors'))
 except BaseException as e:
  rec.update(status='failed',error=repr(e));raise
 finally:
  rec.update(elapsed_seconds=time.monotonic()-start,end_utc=now());write_json(receipt,rec);print(json.dumps(rec),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path)
 args=parser.parse_args()
 if args.out:OUT=args.out
 main()
