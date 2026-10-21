from pathlib import Path
import json,hashlib,subprocess,xml.etree.ElementTree as ET,time
P=Path(__file__).resolve().parent;R=P.parents[2];O=R/'qwen/.runtime/related_numeric_sft_20260928'
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ids={'H02','H03','H08','H12','DA15','DB01','DB08','DB16'}
old=R/'docs/research/transfer-reanalysis-2026-09-26'
jobs=[x for x in read(old/'eval-jobs-v2.json') if x['source_id'] in ids]
keys={x['id']:x for x in read(old/'answer-key.researcher-only.json') if x['source_id'] in ids}
for i,j in enumerate(jobs):j.update(seed=2026093000+i,split='untrained_configuration')
proof=read(R/'qwen/.runtime/proof_numeric_pilot_20260928/proof-jobs.json')[:4]
for i,j in enumerate(proof):j.update(seed=2026093100+i)
jobs+=proof
retention=read(R/'docs/research/program-self-training-2026-09-26/eval-jobs.json')[-4:]
answers=['2*sqrt(7)','15/2','5','6']
for i,(j,a) in enumerate(zip(retention,answers)):
 j.pop('provenance',None);j.update(seed=2026093200+i,split='retention');j['messages'][0]['content']+='\nEnd with a single line of the form Answer: <exact numerical expression>.'
 keys[j['id']]={'id':j['id'],'source_id':j['source_id'],'answer_exact':a}
jobs+=retention
write(O/'main-jobs.json',jobs);write(O/'main-answer-key.json',keys)
xml=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x'],text=True));inventory=[]
for x in xml.findall('.//process_info'):
 if x.findtext('type')!='C+G':continue
 pid=int(x.findtext('pid'));p=Path('/proc')/str(pid)
 inventory.append({'pid':pid,'executable':str((p/'exe').resolve()),'cmdline_sha256':sha(p/'cmdline'),'xml_type':'C+G'})
write(O/'desktop-inventory.json',{'desktop_inventory':inventory})
source=R/'docs/research/transfer-reanalysis-2026-09-26/generate_batch.py'
s=source.read_text().replace('((32768,40960),(81920,98304))','((32768,40960),(81920,98304),(131072,147456))')
(P/'generate_batch.py').write_text(s)
write(O/'main-freeze.json',{'unix':time.time(),'jobs':len(jobs),'sha256':{str(p):sha(p) for p in [P/'PROTOCOL.md',P/'generate_batch.py',O/'main-jobs.json',O/'main-answer-key.json']}})
print('Frozen',len(jobs),'main evaluation jobs; no answers in jobs')
