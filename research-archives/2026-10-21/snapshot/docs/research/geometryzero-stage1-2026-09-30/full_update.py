"""One fresh complete GCPO group; full trainable head; FP32 CPU Adam master."""
import argparse,gc,json,os,resource,time
from pathlib import Path
os.environ.setdefault('HF_HUB_OFFLINE','1');os.environ.setdefault('TOKENIZERS_PARALLELISM','false');os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
import torch
from prepare import HERE,sha,write
class ChunkLogps(torch.autograd.Function):
 @staticmethod
 def forward(ctx,h,w,targets,chunk):
  ctx.shape=h.shape;h=h.reshape(-1,h.shape[-1]);targets=targets.flatten();ctx.save_for_backward(h,w,targets);ctx.chunk=chunk;parts=[]
  for i in range(0,len(h),chunk):
   z=torch.nn.functional.linear(h[i:i+chunk],w).float();parts.append(z.gather(1,targets[i:i+chunk,None]).squeeze(1)-torch.logsumexp(z,dim=-1))
  return torch.cat(parts)
 @staticmethod
 def backward(ctx,grad):
  h,w,t=ctx.saved_tensors;gh=torch.zeros_like(h);gw=torch.zeros_like(w) if ctx.needs_input_grad[1] else None
  for i in range(0,len(h),ctx.chunk):
   hh=h[i:i+ctx.chunk];z=torch.nn.functional.linear(hh,w).float();d=-torch.softmax(z,dim=-1);d.scatter_add_(1,t[i:i+ctx.chunk,None],torch.ones((len(hh),1),device=h.device));d=(d*grad[i:i+ctx.chunk,None]).to(h.dtype)
   gh[i:i+ctx.chunk]=d@w
   if gw is not None:gw.add_(d.T@hh)
  return gh.reshape(ctx.shape),gw,None,None
def logps(model,row):
 ids=row['prompt_ids']+row['completion_ids'];n=len(row['completion_ids']);inp=torch.tensor([ids],device=model.device)
 h=model.model(input_ids=inp,use_cache=False).last_hidden_state[:,len(row['prompt_ids'])-1:len(row['prompt_ids'])+n-1]
 return ChunkLogps.apply(h,model.lm_head.weight,torch.tensor(row['completion_ids'],device=model.device),32)
def objective(lp,old,A):
 ratio=(lp-old).exp();return -torch.minimum(ratio*A,ratio.clamp(.8,1.2)*A).mean()/8
def adam_one(master,m,v,g,step,lr=3e-7):
 m.mul_(.9).add_(g,alpha=.1);v.mul_(.999).addcmul_(g,g,value=.001)
 denom=v.sqrt().div_((1-.999**step)**.5).add_(1e-8);master.addcdiv_(m,denom,value=-lr/(1-.9**step))
def probe(model,row):
 rr=dict(row,completion_ids=row['completion_ids'][:256])
 with torch.no_grad():lp=logps(model,rr).cpu().tolist()
 return dict(id=row['id']+'-'+str(row['sample']),input_ids=rr['prompt_ids']+rr['completion_ids'],prompt_tokens=len(rr['prompt_ids']),logps=lp)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--rows',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();rows=json.loads(a.rows.read_text());assert len(rows)==8 and all(r['finish_reason']=='stop' and 'advantage' in r for r in rows)
 a.out.mkdir(exist_ok=False);start=time.monotonic();receipt=dict(status='running',start_unix=time.time(),rows_sha256=sha(a.rows),source_sha256=sha(__file__),actual_updates=0,objective='mean of eight sequence-mean clipped surrogates; sample-std normalized advantage; full trajectories; KL0; dropout0',lr=3e-7,optimizer='FP32 CPU master and Adam moments; GPU BF16 parameters and gradients',optimizer_resume_tested=False);write(a.out/'receipt.json',receipt)
 try:
  from transformers import AutoModelForCausalLM,AutoTokenizer
  torch.set_num_threads(4);torch.manual_seed(20260930);meta=json.loads((HERE/'model.json').read_text());tick=time.monotonic()
  model=AutoModelForCausalLM.from_pretrained(meta['snapshot'],dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa',local_files_only=True)
  model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.config.use_cache=False
  assert all(p.requires_grad for p in model.parameters());assert getattr(model.config,'attention_dropout',0)==0
  receipt['loading_seconds']=time.monotonic()-tick;named=list(model.named_parameters());params=[p for _,p in named];receipt['trainable_parameters']=sum(p.numel() for p in params)
  model.eval();before=[probe(model,r) for r in rows[:4]];old=[];tick=time.monotonic();fidelity=[]
  for r in rows:
   with torch.no_grad():lp=logps(model,r).detach();old.append(lp.cpu());d=lp-torch.tensor(r['rollout_logps'],device=lp.device)
   fidelity.append(dict(mean_abs=float(d.abs().mean()),max_abs=float(d.abs().max()),rms=float(d.square().mean().sqrt())))
  receipt['old_logp_seconds']=time.monotonic()-tick;receipt['actor_learner']=fidelity;write(a.out/'receipt.json',receipt)
  model.train();model.zero_grad(set_to_none=True);torch.cuda.reset_peak_memory_stats();details=[]
  for r,o in zip(rows,old,strict=True):
   tick=time.monotonic();lp=logps(model,r);loss=objective(lp,o.to(lp.device),r['advantage']);assert torch.isfinite(loss);loss.backward();torch.cuda.synchronize();detail=dict(sample=r['sample'],tokens=len(r['completion_ids']),advantage=r['advantage'],reward=r['total_reward'],seconds=time.monotonic()-tick,loss=float(loss.detach()),train_eval_logp_mean_abs=float((lp.detach()-o.to(lp.device)).abs().mean()),train_eval_logp_max_abs=float((lp.detach()-o.to(lp.device)).abs().max()));details.append(detail);write(a.out/'details.json',details);print(json.dumps(detail),flush=True);del lp,loss;gc.collect()
  receipt['forward_backward_seconds']=sum(d['seconds'] for d in details);norm=torch.nn.utils.clip_grad_norm_(params,1);assert torch.isfinite(norm) and float(norm)>0;receipt['grad_norm']=float(norm)
  tick=time.monotonic();state=[]
  for name,p in named:
   master=p.detach().float().cpu();state.append((name,master,torch.zeros_like(master),torch.zeros_like(master)))
  receipt['optimizer_init_seconds']=time.monotonic()-tick;receipt['cpu_after_init_status']=Path('/proc/self/status').read_text();receipt['cpu_state_gib']=sum(x.numel()*x.element_size() for _,*xs in state for x in xs)/2**30
  tick=time.monotonic();changed=0;changed_elems=0;maximum=0.;optimizer_probe=[]
  for (name,p),(nm,master,m,v) in zip(named,state,strict=True):
   assert name==nm and p.grad is not None and torch.isfinite(p.grad).all();g=p.grad.detach().float().cpu();before_p=p.detach().cpu();adam_one(master,m,v,g,1);updated=master.to(p.dtype);delta=(updated.float()-before_p.float()).abs();mx=float(delta.max());maximum=max(maximum,mx);changed+=mx>0;changed_elems+=int((delta>0).sum());p.data.copy_(updated.to(p.device));p.grad=None
   if len(optimizer_probe)<3:optimizer_probe.append(dict(name=name,step=1,master=master.flatten()[:128].clone(),exp_avg=m.flatten()[:128].clone(),exp_avg_sq=v.flatten()[:128].clone()))
   del g,before_p,updated,delta
  torch.cuda.synchronize();receipt.update(optimizer_seconds=time.monotonic()-tick,actual_updates=1,changed_tensors=changed,changed_elements=changed_elems,max_weight_change=maximum,optimizer_steps=[1]);assert changed>0
  torch.save(optimizer_probe,a.out/'optimizer-probe.pt');loaded=torch.load(a.out/'optimizer-probe.pt',weights_only=True)
  assert all(x['step']==1 and all(torch.equal(x[k],y[k]) for k in ('master','exp_avg','exp_avg_sq')) for x,y in zip(optimizer_probe,loaded,strict=True));receipt['optimizer_probe_roundtrip']=True
  del state,optimizer_probe,loaded;gc.collect();model.eval();after=[probe(model,r) for r in rows[:4]]
  verification=[dict(id=b['id'],input_ids=b['input_ids'],prompt_tokens=b['prompt_tokens'],before_logps=b['logps'],after_logps=c['logps']) for b,c in zip(before,after,strict=True)];write(a.out/'fixed-probes.json',verification)
  tick=time.monotonic();model.save_pretrained(a.out/'model',safe_serialization=True,max_shard_size='2GB');AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True).save_pretrained(a.out/'model')
  from safetensors import safe_open
  sd=model.state_dict();verified=0
  for path in (a.out/'model').glob('*.safetensors'):
   with safe_open(str(path),framework='pt',device='cpu') as f:
    for name in f.keys():assert torch.equal(f.get_tensor(name),sd[name].detach().cpu());verified+=1
  assert verified>=len(named);receipt.update(saved_tensors_verified=verified,save_verify_seconds=time.monotonic()-tick,peak_gpu_allocated_gib=torch.cuda.max_memory_allocated()/2**30,peak_gpu_reserved_gib=torch.cuda.max_memory_reserved()/2**30,peak_cpu_rss_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,status='complete')
 except BaseException as e:receipt.update(status='failed',error=repr(e));raise
 finally:receipt.update(elapsed_seconds=time.monotonic()-start,end_unix=time.time());write(a.out/'receipt.json',receipt);print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
