"""One independent, full-trajectory GRPO-style numeric update for feasibility."""
import argparse,gc,hashlib,importlib.util,json,math,os,sys,time
from pathlib import Path
os.environ.setdefault('HF_HUB_OFFLINE','1');os.environ.setdefault('TOKENIZERS_PARALLELISM','false');os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT))
import torch
from qwen.grpo_loss import frozen_head_logps,token_policy_loss
from signal_analysis import group,sha,write
MODULES=['q_proj','k_proj','v_proj','o_proj','in_proj_qkv','in_proj_z','out_proj','gate_proj','up_proj','down_proj']
def imported(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def hidden(model,row):
    ids=torch.tensor([row['prompt_ids']+row['completion_ids']],device='cuda');n=len(row['completion_ids'])
    h=model.get_base_model().model(input_ids=ids,use_cache=False).last_hidden_state
    return h[:,len(row['prompt_ids'])-1:len(row['prompt_ids'])+n-1],torch.tensor([row['completion_ids']],device='cuda')
def short_probe(model,row):
    # The prefix is used ONLY for actor/learner fidelity, never for the update.
    ids=row['completion_ids'][:min(1024,len(row['completion_ids']))];s=dict(row,completion_ids=ids)
    with torch.no_grad():
        h,t=hidden(model,s);lp=frozen_head_logps(h,model.get_base_model().lm_head.weight,t,temperature=1,chunk_size=64).flatten().cpu().tolist()
    return dict(id=row['id']+'-'+str(row['sample']),input_ids=row['prompt_ids']+ids,prompt_tokens=len(row['prompt_ids']),logps=lp)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rows',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    rows=json.loads(a.rows.read_text());g=group(rows)
    if len(rows)!=4 or len({r['id'] for r in rows})!=1 or not g['eligible'] or not g['mixed']:raise ValueError('requires one complete mixed four-sample group')
    if any(r['policy_adapter_sha256'] is not None or r['finish_reason']!='stop' or r['advantage']!=v for r,v in zip(rows,g['advantages'])):raise ValueError('off-policy/censored/advantage mismatch')
    if any(len(r['prompt_ids'])+len(r['completion_ids'])>40960 for r in rows):raise ValueError('context bound; no truncation')
    meta_path=ROOT/'docs/research/qwen35-self-materials-2026-09-23/model.json';meta=json.loads(meta_path.read_text())
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    offmod=imported('verified_activation_offload',ROOT/'docs/research/answer-opd-complete-2026-09-26/streamed_kl.py')
    mapping=imported('verified_mapping',ROOT/'docs/research/answer-opd-pilot-2026-09-26/train_worker.py')
    receipt=dict(status='running',start_unix=time.time(),driver_sha256=sha(__file__),rows_sha256=sha(a.rows),model_revision=meta['revision'],objective='token-normalized clipped policy objective; reward minus group mean; T=1; beta=0; one fresh rollout / one update',denominator=sum(len(r['completion_ids']) for r in rows),rewards=[r['reward'] for r in rows],advantages=g['advantages'],planned_updates=1,actual_updates=0,no_training_truncation=True,parameters=dict(rank=8,alpha=16,dropout=0,lr=5e-6,grad_clip=1,seed=2026093060,activation_offload_cpu_gib=12),source_sha256={str(p):sha(p) for p in [ROOT/'qwen/grpo_loss.py',ROOT/'docs/research/answer-opd-complete-2026-09-26/streamed_kl.py',ROOT/'docs/research/answer-opd-pilot-2026-09-26/train_worker.py']})
    write(out/'receipt.json',receipt)
    try:
        from peft import LoraConfig,TaskType,get_peft_model
        from transformers import AutoModelForCausalLM
        torch.set_num_threads(4);torch.manual_seed(2026093060);torch.cuda.manual_seed_all(2026093060)
        tick=time.monotonic();model=AutoModelForCausalLM.from_pretrained(meta['snapshot'],dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa',local_files_only=True)
        model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=0,target_modules=MODULES,bias='none',task_type=TaskType.CAUSAL_LM))
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.enable_input_require_grads();model.config.use_cache=False
        receipt['loading_seconds']=time.monotonic()-tick
        named=[(n,p) for n,p in model.named_parameters() if p.requires_grad];params=[p for n,p in named]
        if any('lora_' not in n for n,p in named) or model.get_base_model().lm_head.weight.requires_grad:raise ValueError('unexpected trainable base/head')
        before={n:p.detach().float().cpu().clone() for n,p in named};optimizer=torch.optim.AdamW(params,lr=5e-6,weight_decay=0)
        receipt.update(trainable_parameters=sum(p.numel() for p in params),lora_dtypes=sorted({str(p.dtype) for p in params}))
        # Same short causal inputs and inference mode for before/after checks.
        model.eval();probes=[short_probe(model,r) for r in rows];model.train()
        optimizer.zero_grad(set_to_none=True);torch.cuda.reset_peak_memory_stats();details=[]
        for row,advantage in zip(rows,g['advantages']):
            tick=time.monotonic();tracker=offmod.ActivationOffload(model.parameters(),True,12*2**30,4*2**30)
            with tracker.context():h,t=hidden(model,row)
            lp=frozen_head_logps(h,model.get_base_model().lm_head.weight,t,temperature=1,chunk_size=64);old=lp.detach()
            actor=torch.tensor([row['rollout_logps']],device='cuda',dtype=torch.float32)
            delta=old-actor
            fidelity=dict(mean_abs=float(delta.abs().mean()),max_abs=float(delta.abs().max()),rms=float(delta.square().mean().sqrt()))
            # This precision threshold was fixed before the first GPU update.
            if fidelity['mean_abs']>0.02 or fidelity['max_abs']>0.2:raise RuntimeError('Actor/learner fidelity outside predeclared bound: '+str(fidelity))
            loss=token_policy_loss(lp,old,torch.tensor([advantage],device='cuda'),torch.ones_like(lp),receipt['denominator'])
            if not torch.isfinite(loss):raise ValueError('nonfinite loss')
            loss.backward();torch.cuda.synchronize()
            detail=dict(sample=row['sample'],reward=row['reward'],advantage=advantage,tokens=len(row['completion_ids']),seconds=time.monotonic()-tick,loss=float(loss.detach()),actor_learner=fidelity,offload=tracker.stats())
            details.append(detail);write(out/'details.json',details);print(json.dumps(detail),flush=True)
            del h,t,lp,old,actor,delta,loss,tracker;gc.collect();torch.cuda.empty_cache()
        tick=time.monotonic();norm=torch.nn.utils.clip_grad_norm_(params,1)
        if not torch.isfinite(norm) or float(norm)<=0:raise ValueError('zero/nonfinite gradient')
        optimizer.step();optimizer.zero_grad(set_to_none=True);torch.cuda.synchronize();receipt['optimizer_seconds']=time.monotonic()-tick;receipt['actual_updates']=1
        changes={n:float((p.detach().float().cpu()-before[n]).abs().max()) for n,p in named};changed=sum(v>0 for v in changes.values())
        if not changed:raise ValueError('no weight update')
        receipt.update(grad_norm_before_clipping=float(norm),changed_lora_tensors=changed,total_lora_tensors=len(named),max_weight_change=max(changes.values()),forward_backward_seconds=sum(d['seconds'] for d in details),peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30)
        tick=time.monotonic();model.eval();verification=[]
        for row,b in zip(rows,probes):
            p=short_probe(model,row);verification.append(dict(id=b['id'],input_ids=b['input_ids'],prompt_tokens=b['prompt_tokens'],before_logps=b['logps'],after_logps=p['logps']))
        receipt['post_update_probe_seconds']=time.monotonic()-tick;write(out/'fixed-probes.json',verification)
        tick=time.monotonic();model.save_pretrained(out/'adapter',safe_serialization=True)
        receipt['saved_adapter_tensors_verified']=mapping.verify_saved_adapter(model,out/'adapter')
        mapped=mapping.export_vllm_adapter(out/'adapter',out/'adapter-vllm');receipt['mapping']=mapped
        state=optimizer.state_dict();torch.save(state,out/'optimizer.pt');loaded=torch.load(out/'optimizer.pt',map_location='cpu',weights_only=True)
        if state['param_groups']!=loaded['param_groups'] or state['state'].keys()!=loaded['state'].keys():raise ValueError('optimizer reload differs')
        for k,values in state['state'].items():
            for n,v in values.items():
                vv=loaded['state'][k][n]
                if torch.is_tensor(v):
                    if not torch.equal(v.cpu(),vv):raise ValueError('optimizer tensor mismatch')
                elif v!=vv:raise ValueError('optimizer scalar mismatch')
        steps=sorted({int(s['step'].item()) for s in loaded['state'].values()})
        if steps!=[1]:raise ValueError('wrong actual step count')
        receipt.update(save_reload_seconds=time.monotonic()-tick,optimizer_steps=steps,optimizer_sha256=sha(out/'optimizer.pt'),adapter_sha256=sha(out/'adapter/adapter_model.safetensors'),vllm_adapter_sha256=sha(out/'adapter-vllm/adapter_model.safetensors'),status='complete')
    except BaseException as e:receipt.update(status='failed',error=repr(e));raise
    finally:
        receipt.update(end_unix=time.time(),elapsed_seconds=time.monotonic()-started);write(out/'receipt.json',receipt);print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
