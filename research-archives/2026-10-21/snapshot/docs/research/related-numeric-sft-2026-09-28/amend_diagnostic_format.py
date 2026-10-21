from pathlib import Path
import json,hashlib,time,shutil
P=Path(__file__).resolve().parent;R=P.parents[2];O=R/'qwen/.runtime/related_numeric_sft_20260928'
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not any((O/f'{a}-diagnostic').exists() for a in ['base','sft-a','sft-b'])
d=O/'pre-diagnostic-prompt-amendment';d.mkdir(exist_ok=False)
for n in ['diagnostic-jobs.json','diagnostic-answer-key.json','data-freeze.json']:shutil.copy2(O/n,d/n)
train=read(O/'train.json');prefix=train[0]['messages'][0]['content'].split('\n\n',1)[0]+'\n\n'
provenance={r['id']:r for r in read(O/'data-provenance.json')};keys=read(O/'diagnostic-answer-key.json');jobs=read(O/'diagnostic-jobs.json')
byid={r['id']:r for r in train}
for j in jobs:
 rid=keys[j['id']]['provenance_id'];row=provenance[rid]
 j['messages']=[{'role':'user','content':prefix+row['problem_en']}]
 if j['split']=='trained_example':assert j['messages']==byid[rid]['messages']
write(O/'diagnostic-jobs.json',jobs)
f=read(O/'data-freeze.json');f.update(diagnostic_format_amendment=str(P/'DIAGNOSTIC_PROMPT_AMENDMENT.md'),amendment_unix=time.time())
f['sha256'][str(O/'diagnostic-jobs.json')]=sha(O/'diagnostic-jobs.json')
f['sha256'][str(P/'DIAGNOSTIC_PROMPT_AMENDMENT.md')]=sha(P/'DIAGNOSTIC_PROMPT_AMENDMENT.md')
f['sha256'][str(Path(__file__))]=sha(Path(__file__))
write(O/'data-freeze.json',f)
print('20 diagnostic jobs use exact training prefix; all 10 seen prompts exactly match training; no diagnostic outputs existed.')
