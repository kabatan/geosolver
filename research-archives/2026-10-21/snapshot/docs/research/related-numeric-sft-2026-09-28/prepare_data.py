"""Freeze solver-derived numeric-only training and diagnostic examples."""
from pathlib import Path
import json,hashlib,time,collections,math
import generate_a,generate_b
P=Path(__file__).resolve().parent;R=P.parents[2];O=R/'qwen/.runtime/related_numeric_sft_20260928'
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
TRAIN_PREFIX='Solve the following numerical geometry problem. Give only the requested numerical value, with at least 10 significant digits when appropriate. Do not give a proof or explanation.\n\n'
EVAL_PREFIX='Solve the following geometry problem. Give the numerical answer and explain your reasoning in English. You have no access to tools.\n\n'
EVAL_SUFFIX='\n\nEnd with a single line of the form Answer: <numerical value>. Give at least 8 significant digits when appropriate.'
rows=generate_a.generate(seed=2026092803,per_type=12)+generate_b.generate(seed=2026092804,per_type=12)
by=collections.defaultdict(list)
for r in rows:by[r['source_id']].append(r)
assert len(by)==10 and all(len(v)==12 for v in by.values())
train=[];jobs=[];keys={};provenance=[];i=0
for source,examples in by.items():
 sigs=[tuple(round(float(v),8) for v in r['shape_signature']) for r in examples]
 assert len(set(sigs))==12,source
 assert len({r['target'] for r in examples[:8]})==8,source
 for j,r in enumerate(examples):
  rid=f'{source}-variant-{j+1:02d}';p=dict(r,id=rid,split='train' if j<8 else 'heldout' if j<10 else 'reserve');provenance.append(p)
  assert math.isfinite(float(r['target']))
  assert not any(s in r['problem_en'].lower() for s in ['dumpty','humpty','symmedian','answer:','therefore'])
  if j<8:train.append({'id':rid,'source_id':source,'kind':'numeric','messages':[{'role':'user','content':TRAIN_PREFIX+r['problem_en']}],'target':r['target']})
  if j in (0,8):
   jid=f'diagnostic-{source.lower()}-'+('trained' if j==0 else 'newshape')
   jobs.append({'id':jid,'source_id':source,'pack_id':r['pack_id'],'seed':2026093300+i,'split':'trained_example' if j==0 else 'new_shape','messages':[{'role':'user','content':EVAL_PREFIX+r['problem_en']+EVAL_SUFFIX}]})
   keys[jid]={'id':jid,'source_id':source,'answer_exact':r['target'],'provenance_id':rid};i+=1
write(O/'train.json',train);write(O/'data-provenance.json',provenance);write(O/'diagnostic-jobs.json',jobs);write(O/'diagnostic-answer-key.json',keys)
config=read(R/'docs/research/program-self-training-2026-09-26/config-numeric.json')
for k in ['selection_receipt','selection_receipt_sha256','generation_length_amendment_sha256']:config.pop(k,None)
config.update(dataset=str(O/'train.json'),dataset_sha256=sha(O/'train.json'),save_checkpoints=[],protocol_sha256=sha(P/'PROTOCOL.md'))
cont=R/'docs/research/program-self-training-followup-2026-09-26/train_continue.py'
for arm,seed in [('sft-a',2026092701),('sft-b',2026092901)]:
 c=dict(config,seed=seed,updates=32);write(P/f'config-{arm}-32.json',c)
 c.update(updates=128,prior_checkpoint=str(O/f'{arm}-train32/final'),extension_wrapper_sha256=sha(cont));write(P/f'config-{arm}-128.json',c)
files=[P/'PROTOCOL.md',P/'generate_a.py',P/'generate_b.py',Path(__file__),O/'train.json',O/'data-provenance.json',O/'diagnostic-jobs.json',O/'diagnostic-answer-key.json']+list(P.glob('config-sft-*.json'))
write(O/'data-freeze.json',{'unix':time.time(),'training_examples':len(train),'constructed_shapes':len(rows),'diagnostic_jobs':len(jobs),'sources':list(by),'teacher':'numeric only .17g; original construction oracle','sha256':{str(p):sha(p) for p in files}})
print(json.dumps({'train':len(train),'constructed':len(rows),'diagnostic':len(jobs),'sources':list(by)},ensure_ascii=False))
