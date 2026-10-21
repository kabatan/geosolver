import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import torch
from qwen.grpo_loss import frozen_head_logps,sampling_correction,token_policy_loss
start=time.monotonic();torch.set_num_threads(2)
old=torch.tensor([[-2.,-1.,-.5],[-2.,-1.,-.5]])
d=torch.tensor([[.2,-.2,1.],[.2,-.2,1.]])
w,m=sampling_correction(old,old-d,cap=2)
torch.testing.assert_close(w,d.exp().clamp(max=2));assert abs(m['clipped_fraction']-1/3)<1e-6
x=old.clone().requires_grad_();adv=torch.tensor([.5,-.5]);loss=token_policy_loss(x,old,adv,torch.ones_like(x),6,importance_weights=w);loss.backward()
torch.testing.assert_close(x.grad,-adv[:,None]*w/6)
results=[]
for dtype in (torch.float32,torch.bfloat16):
 torch.manual_seed(32);h=torch.randn(2,7,9,dtype=dtype,requires_grad=True);weight=torch.randn(29,9,dtype=dtype);target=torch.randint(29,(2,7))
 dense=(h@weight.T).float().log_softmax(-1).gather(-1,target[...,None]).squeeze(-1);o=dense.detach();imp=torch.linspace(.7,1.3,14).reshape(2,7);mask=torch.tensor([[1,1,1,0,0,0,0],[1,1,1,1,1,1,1]])
 ref=torch.autograd.grad(token_policy_loss(dense,o,adv,mask,10,importance_weights=imp),h)[0]
 c=h.detach().clone().requires_grad_();lp=frozen_head_logps(c,weight,target,temperature=1,chunk_size=3);token_policy_loss(lp,o,adv,mask,10,importance_weights=imp).backward()
 error=float((c.grad.float()-ref.float()).norm()/ref.float().norm());assert error<(3e-6 if dtype==torch.float32 else 2*torch.finfo(dtype).eps)
 torch.testing.assert_close(lp,dense,atol=3e-6,rtol=3e-6);results.append(dict(dtype=str(dtype),relative_gradient_error=error))
p=ROOT/'qwen/.runtime/numeric_rl_feasibility_20260930/importance-cpu-validation.json';source=Path(__file__)
p.write_text(json.dumps(dict(status='pass',seconds=time.monotonic()-start,tests='closed-form positive/negative advantage TIS gradient and dense full-vocabulary weighted head gradient (FP32/BF16)',results=results,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()),indent=2)+'\n');print(p.read_text())
