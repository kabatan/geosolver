"""Deterministic selection; actor jobs contain no labels."""
import hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];RUN=ROOT/'qwen/.runtime/geometryzero_stage1_20260930'
def write(p,x):
 p=Path(p);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 spec=importlib.util.spec_from_file_location('templates',ROOT/'docs/research/qwen35-diverse-sft-2026-09-24/english_templates.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 rows=[json.loads(s) for s in (ROOT/'benchmarks/humpty_configurations_v2/training_variants.jsonl').read_text().splitlines()];sel=[]
 for prefix in ('H','DA','DB'):sel.extend([r for r in rows if r['variant']=='v0' and r['id'].startswith(prefix)][:8])
 assert len(sel)==24
 jobs=[];labels={}
 fmt='Output the thinking process in <think> </think> and final answer (number) in <answer> </answer> tags.'
 instructions={'without':'','with':'You must edit the geometry specification to construct auxiliary lines in the thinking process, which should be marked with <auxiliary> </auxiliary> tags.','main':'You have a coin flip decision to make, whether to edit the geometry specification to construct auxiliary lines in the thinking process, which should be marked with <auxiliary> </auxiliary> tags.'}
 for i,r in enumerate(sel):
  problem=m.NUMERIC_EN[r['id']].format(**r['givens']);labels[r['id']]=dict(answer_exact=r['answer_exact'],givens=r['givens'],problem_en=problem,problem_ja=r['problem'])
  for k,g in enumerate(('without','with','main')):
   text='Geometry specification and question:\n'+problem+'\n'+fmt+'\n'+instructions[g]
   jobs.append(dict(id=r['id']+'-'+g,problem_id=r['id'],group=g,messages=[dict(role='user',content=text)],seed=2026093000+i*3+k))
 write(RUN/'jobs.json',jobs);write(RUN/'labels.json',labels)
 write(HERE/'selection.json',dict(ids=list(labels),jobs_sha256=sha(RUN/'jobs.json'),labels_sha256=sha(RUN/'labels.json'),dataset_sha256=sha(ROOT/'benchmarks/humpty_configurations_v2/training_variants.jsonl'),translation_sha256=sha(ROOT/'docs/research/qwen35-diverse-sft-2026-09-24/english_templates.py')))
if __name__=='__main__':main()
