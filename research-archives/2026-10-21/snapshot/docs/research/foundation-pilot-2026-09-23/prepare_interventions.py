"""Freeze the bounded FT intervention and its inference-only comparator."""
import hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
train=json.loads((D/'foundation-train.json').read_text())
examples=[x for x in train if x['label_shift']==0 and x['id'].split('-')[0] in ['T01','T06','T19','T23']]
prefix='Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.\n\nHere are four examples of the desired mathematical care; they are not hints to the new problem.\n\n'
for x in examples:prefix+='Example problem: '+x['problem']+'\nExample answer: '+x['answer']+'\n\n'
rows=json.loads((D/'confirmation-jobs.json').read_text())
for r in rows:r['problem']=prefix+'New problem:\n'+r['problem']
out=D/'confirmation-prompt-jobs.json';assert not out.exists()
out.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
old=Path('docs/research/model-fit-2026-09-23/jobs.json')
target=[r|{'stratum':'target_development'} for r in json.loads(old.read_text()) if r['stratum']=='unassisted']
(D/'target-dev-jobs.json').write_text(json.dumps(target,ensure_ascii=False,indent=2)+'\n')
long=[r for r in json.loads((D/'screen-jobs.json').read_text()) if r['id'] in ['F02','F08','F11']]
(D/'long-diagnostic-jobs.json').write_text(json.dumps(long,ensure_ascii=False,indent=2)+'\n')
protocol=dict(
 model='qwen3_4b',rationale='Control model shows completed invalid reasoning as well as truncation. Test a cheap repair option alongside stronger pretrained alternatives; do not assume FT is required for every model.',
 n_structures=24,n_examples=96,epochs=3,effective_batch=4,micro_batch=1,updates=72,
 seed=2026092321,lr=1e-4,min_lr=1e-5,warmup_updates=4,weight_decay=0.0,grad_clip=1.0,
 dtype='bfloat16',attention='sdpa',lora_rank=32,lora_alpha=64,lora_dropout=0.0,
 modules='q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj',
 loss='Assistant-only; brief authored mathematical plan, closing think tag, complete proof, EOS. No truncation of teacher answers.',
 checkpoint='One final adapter only; no checkpoint selected using confirmation or target results.',
 comparison='Fixed confirmation before/after at the same 8192 completion cap and seeds; four-example prompt comparator. A small 32768-token screen diagnostic separates incomplete search from mathematical incapacity.',
 target='Four already exposed target-development numerical configurations, not final proof evaluation; no hints are supplied. Japanese wording retained exactly from the earlier audit. Evaluate both before and after, cap32768. Never use their answers for this foundation FT.',
 train_sha256=sha(D/'foundation-train.json'),confirmation_sha256=sha(D/'confirmation-jobs.json'),prompt_sha256=sha(out),target_sha256=sha(D/'target-dev-jobs.json'),
 limits='One fixed SFT recipe on one seed; a feasibility intervention, not a conclusive estimate of attainable FT quality. Label permutations do not create independent configurations. No long target RL.')
(D/'sft-protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
