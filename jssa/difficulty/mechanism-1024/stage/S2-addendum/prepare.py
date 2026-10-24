"""Freeze S2 reuse, normal frozen source, scripts and rules before numerical work."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent
S2=OUT.parent/'S2'
REPO=OUT.parents[4]
FROZEN=Path('/tmp/mech-inv-clean/src')
sys.dont_write_bytecode=True
sys.path.insert(0,str(FROZEN))
from geosolver.runtime.integrity import source_tree_hash

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
 text=json.dumps(x,ensure_ascii=False,indent=2)+'\n'
 assert len(text.encode())<3_000_000
 p.write_text(text)
assert not (OUT/'pre-run-hashes.json').exists()
old=json.loads((S2/'pre-run-hashes.json').read_text())
assert source_tree_hash()==old['source_hash']
assert (OUT/'addendum.md').read_bytes()==subprocess.check_output(['git','-C',str(REPO),'show','f2a2ad93:jssa/difficulty/mechanism-1024/stage/S2-addendum/addendum.md'])
for rel,h in old['source_files'].items():
 assert sha(FROZEN.parent/rel)==h,rel
for name in ['s2_common.py','pslq_wrapper.py','frozen_polynomial_search.py']:
 assert (OUT/name).read_bytes()==(S2/('worker.py' if name=='s2_common.py' else name)).read_bytes()
import csv
rows=list(csv.DictReader((S2/'per-condition.csv').open()))
keys=['AIME-2019-I-12__length','AIME-2019-I-12__area','AIME-2021-I-13','HMMT-2010-FEB-GEO-02']
assert {r['key'] for r in rows if r['outcome']=='到達不可'}==set(keys)
(OUT/'inputs').mkdir(exist_ok=True)
items=[]
for key in keys:
 assert len([r for r in rows if r['key']==key and r['outcome']=='到達不可'])==6
 dest=OUT/'inputs'/(key+'.json'); dest.write_bytes((S2/'inputs'/dest.name).read_bytes())
 item=next(i for i in json.loads((S2/'schedule.json').read_text()) if i['key']==key)
 items.append(item)
save(OUT/'schedule.json',items)
files=[OUT/'addendum.md',OUT/'rules.md',OUT/'schedule.json',*OUT.glob('*.py'),*(OUT/'inputs').glob('*.json')]
# These reused evidence bytes include every S2 artifact and the preregistration.
s2files={str(p):sha(p) for p in sorted(S2.rglob('*')) if p.is_file()}
files.append(OUT.parent.parent/'preregistration-7.md')
manifest=dict(created_utc=datetime.now(timezone.utc).isoformat(),source_commit=old['source_commit'],
 source_hash=source_tree_hash(),frozen_source=str(FROZEN),source_files=old['source_files'],
 files={str(p):sha(p) for p in sorted(files)},s2_files=s2files,
 parallelism=2,cpus=sorted(os.sched_getaffinity(0))[-2:],python=old['python'],threads=old['threads'],
 host=platform.node(),platform=platform.platform(),python_version=sys.version,
 problem_count=4,conditions_per_problem=6,retries=0,reference_dps=700,maximum_achieved_digits=500,
 limits=dict(stage_seconds=180,refinement_total_seconds=600,refinement_outer_seconds=608,pslq_outer_seconds=188,memory_bytes=3<<30),
 normal_config=dict(schedule_dps=[50,100,120],closure_schedule_dps=[120,250,350,500],max_stage_iters=80),
 prediction_commit='f2a2ad93',note='post hoc supplement; preregistration 7 main judgments remain undetermined')
save(OUT/'pre-run-hashes.json',manifest)
(OUT/'progress.md').write_text('# S2 補遺 進捗\n\n- '+manifest['created_utc']+' 規則・入力・凍結src・全実行コードのhash固定。実験未開始。4量24条件、並列2、再試行なし。\n')
print(json.dumps({k:manifest[k] for k in ['created_utc','source_hash','cpus','python']},ensure_ascii=False))
