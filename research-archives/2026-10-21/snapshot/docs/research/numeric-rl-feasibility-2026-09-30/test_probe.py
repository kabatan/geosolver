"""Meaningful CPU checks for reward masks and the streamed policy derivative."""
import importlib.util,json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
import torch
from signal_analysis import score,group
from qwen.grpo_loss import frozen_head_logps,token_policy_loss
class ProbeTests(unittest.TestCase):
    def test_decimal_reward_is_not_string_equality(self):
        key=dict(answer='2.6121865084394753')
        self.assertEqual(score(dict(raw_text='Answer: 2.6121865',finish_reason='stop'),key)['reward'],1)
        self.assertEqual(score(dict(raw_text='Answer: 2.61',finish_reason='stop'),key)['reward'],0)
    def test_last_commitment_not_earlier_correct_number(self):
        r=score(dict(raw_text='Answer: 2\nCorrection. Answer: 3',finish_reason='stop'),dict(answer='2'))
        self.assertEqual(r['reward'],0)
    def test_censor_has_no_failure_reward(self):
        r=score(dict(raw_text='Answer: 2',finish_reason='length'),dict(answer='2'))
        self.assertIsNone(r['reward']);self.assertFalse(group([r,dict(reward=1),dict(reward=0),dict(reward=0)])['eligible'])
    def test_mixed_group_signal(self):
        self.assertEqual(group([dict(reward=x) for x in [1,0,1,0]])['advantages'],[.5,-.5,.5,-.5])
        self.assertFalse(group([dict(reward=0)]*4)['mixed'])
        self.assertFalse(group([dict(reward=1)]*4)['mixed'])
    def test_full_vocabulary_value_and_policy_gradient(self):
        torch.manual_seed(5);x=torch.randn(1,11,7,requires_grad=True);w=torch.randn(31,7);targets=torch.randint(31,(1,11))
        dense=(x@w.T).log_softmax(-1).gather(-1,targets[...,None]).squeeze(-1)
        dg,=torch.autograd.grad(token_policy_loss(dense,dense.detach(),torch.tensor([.75]),torch.ones_like(dense),25),x)
        y=x.detach().clone().requires_grad_();lp=frozen_head_logps(y,w,targets,temperature=1,chunk_size=3)
        torch.testing.assert_close(lp,dense,atol=1e-6,rtol=1e-6)
        token_policy_loss(lp,lp.detach(),torch.tensor([.75]),torch.ones_like(lp),25).backward()
        torch.testing.assert_close(y.grad,dg,atol=1e-7,rtol=1e-5)
        z=x.detach().clone().requires_grad_();ll=frozen_head_logps(z,w,targets,temperature=1,chunk_size=3)
        token_policy_loss(ll,ll.detach(),torch.tensor([-.75]),torch.ones_like(ll),25).backward()
        torch.testing.assert_close(z.grad,-dg,atol=1e-7,rtol=1e-5)
    def test_actual_qwen35_causal_alignment_and_lora_gradient(self):
        path=HERE.parent/'answer-opd-complete-2026-09-26/test_capacity_mlp_cpu.py'
        sys.path.insert(0,str(path.parent));s=importlib.util.spec_from_file_location('tiny_qwen_check',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
        torch.set_num_threads(2);model=m.make_model(torch.float32);model.train()
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
        p=[1,2,3];c=list(range(8,25));ids=torch.tensor([p+c]);target=torch.tensor([c])
        full=model(input_ids=ids,use_cache=False,logits_to_keep=len(c)+1).logits[:,:-1]
        dense=full.log_softmax(-1).gather(-1,target[...,None]).squeeze(-1)
        token_policy_loss(dense,dense.detach(),torch.tensor([.5]),torch.ones_like(dense),len(c)).backward()
        reference={n:p.grad.detach().clone() for n,p in model.named_parameters() if p.requires_grad}
        model.zero_grad(set_to_none=True)
        h=model.get_base_model().model(input_ids=ids,use_cache=False).last_hidden_state[:,len(p)-1:len(p)+len(c)-1]
        chunk=frozen_head_logps(h,model.get_base_model().lm_head.weight,target,temperature=1,chunk_size=3)
        torch.testing.assert_close(chunk,dense,atol=1e-6,rtol=1e-6)
        token_policy_loss(chunk,chunk.detach(),torch.tensor([.5]),torch.ones_like(chunk),len(c)).backward()
        self.assertGreater(sum(float(g.square().sum()) for g in reference.values()),0)
        for n,p in model.named_parameters():
            if p.requires_grad:torch.testing.assert_close(p.grad,reference[n],atol=1e-7,rtol=1e-4)
if __name__=='__main__':unittest.main()
