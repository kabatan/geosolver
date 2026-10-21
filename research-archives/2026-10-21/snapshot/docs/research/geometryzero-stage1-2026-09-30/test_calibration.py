"""Meaningful equivalence checks before using the custom head/CPU optimizer."""
import ast,json,re,unittest
from pathlib import Path
import torch
from full_update import ChunkLogps,objective,adam_one
from signals import score,normalize,mask,mask_bounds
from prepare import HERE,write,sha
class Tokenizer:
 def encode(self,x):return list(range(len(x)))
class Tests(unittest.TestCase):
 def test_head_dense_backward(self):
  torch.manual_seed(11);h=torch.randn(1,7,5,dtype=torch.double,requires_grad=True);w=torch.randn(13,5,dtype=torch.double,requires_grad=True);t=torch.randint(13,(7,));g=torch.randn(7)
  # Implementation intentionally computes FP32 softmax, including with a double toy.
  z=torch.nn.functional.linear(h,w).reshape(7,13).float();expected=z.log_softmax(-1).gather(1,t[:,None]).flatten();(expected*g).sum().backward();eh=h.grad.clone();ew=w.grad.clone();h.grad=None;w.grad=None
  actual=ChunkLogps.apply(h,w,t,3);(actual*g).sum().backward();torch.testing.assert_close(actual,expected,atol=1e-6,rtol=1e-6);torch.testing.assert_close(h.grad,eh,atol=1e-6,rtol=1e-6);torch.testing.assert_close(w.grad,ew,atol=1e-6,rtol=1e-6)
 def test_optimizer_two_steps(self):
  p=torch.tensor([.1,-.2,0.],requires_grad=True);master=p.detach().clone();m=torch.zeros_like(p);v=torch.zeros_like(p);opt=torch.optim.AdamW([p],lr=3e-7,betas=(.9,.999),eps=1e-8,weight_decay=0)
  for step,g in enumerate((torch.tensor([.2,-.4,1e-5]),torch.tensor([-.1,.9,1.])),1):p.grad=g;opt.step();adam_one(master,m,v,g,step);torch.testing.assert_close(master,p,atol=1e-10,rtol=1e-7)
 def test_full_model_checkpoint_path(self):
  from transformers import Qwen2Config,Qwen2ForCausalLM
  from full_update import logps
  cfg=Qwen2Config(vocab_size=31,hidden_size=16,intermediate_size=32,num_hidden_layers=2,num_attention_heads=2,num_key_value_heads=2,tie_word_embeddings=True,attention_dropout=0)
  cfg._attn_implementation='sdpa';model=Qwen2ForCausalLM(cfg);row=dict(prompt_ids=[1,2,3],completion_ids=[4,5,6,7])
  ids=torch.tensor([[1,2,3,4,5,6,7]]);z=model(input_ids=ids,use_cache=False).logits[:,2:6].float();dense=z.log_softmax(-1).gather(-1,torch.tensor([[[4],[5],[6],[7]]])).flatten();dense.sum().backward();expected={n:p.grad.clone() for n,p in model.named_parameters()};model.zero_grad();model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});actual=logps(model,row);actual.sum().backward();torch.testing.assert_close(actual,dense,atol=1e-6,rtol=1e-6)
  for n,p in model.named_parameters():torch.testing.assert_close(p.grad,expected[n],atol=2e-6,rtol=2e-5)
 def test_normalization_mask_censor(self):
  xs=[0,0,0,0,0,0,0,1];torch.testing.assert_close(torch.tensor(normalize(xs)),(torch.tensor(xs,dtype=torch.float32)-.125)/(torch.tensor(xs,dtype=torch.float32).std()+1e-9));self.assertEqual(mask(xs,[0]*8),1);self.assertEqual(mask([0]*8,xs),-1);self.assertIsNone(mask_bounds([None]*8,[0]*8)['certain_mask'])
 def test_single_answer_tolerance_and_censor(self):
  def s(text,end='stop'):return score(dict(raw_text=text,finish_reason=end),'32/5',Tokenizer())
  self.assertEqual(s('<think>ok</think><answer>6.4</answer>')['strict'],1);self.assertEqual(s('<think>ok</think><answer>6.5</answer>')['relaxed'],1);self.assertEqual(s('<think>ok</think><answer>6.5</answer>')['strict'],0);self.assertIsNone(s('<answer>6.4</answer>','length')['relaxed']);self.assertEqual(s('<answer>5</answer>')['relaxed'],0);self.assertEqual(s('<answer>5</answer>')['literal_fallback'],1);self.assertEqual(s('<answer>5, 6.4</answer>')['relaxed'],0)
 def test_upstream_format_aux_length(self):
  path=HERE/'upstream/workspace__reward__reward_utils.py';tree=ast.parse(path.read_text());wanted={'format_reward_func','aux_line_reward_v2_func','length_reward_func','__get_tokens'};ns={'re':re,'__text_tokenizer':Tokenizer()}
  tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted];exec(compile(tree,str(path),'exec'),ns)
  for text in ('<think>x</think><answer>6.4</answer>','<think><auxiliary></auxiliary></think><answer>5</answer>','junk','x'*1000):
   got=score(dict(raw_text=text,finish_reason='stop'),'32/5',Tokenizer());self.assertEqual(got['format'],ns['format_reward_func'](text));self.assertEqual(got['aux'],ns['aux_line_reward_v2_func'](text));self.assertEqual(got['length'],ns['length_reward_func'](text,max_length=900,beta=.5))
 def test_sequence_objective(self):
  lp=torch.tensor([-.4,-1.2],requires_grad=True);old=lp.detach();loss=objective(lp,old,2);loss.backward();torch.testing.assert_close(lp.grad,torch.full_like(lp,-2/16));self.assertAlmostEqual(float(loss.detach()),-.25)
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);r=unittest.TextTestRunner(verbosity=2).run(suite);write(HERE/'cpu-tests.json',dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),success=r.wasSuccessful(),source_sha256={p.name:sha(p) for p in (HERE/'full_update.py',HERE/'signals.py',Path(__file__))}));raise SystemExit(0 if r.wasSuccessful() else 1)
