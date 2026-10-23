"""Read-only aggregation of existing references and run-level set relations."""
import pathlib,json,csv,sys,collections,hashlib
OUT=pathlib.Path(__file__).resolve().parent;ROOT=OUT.parents[3]
sys.path[:0]=['/tmp/posthoc20-clean/src','/tmp/posthoc20-clean']
from benchmarks.research_runner import reference_expressions
from geosolver.exact import describe_exact
sources=[]
def cases(rel):
 p=ROOT/rel;sources.append(p)
 return [json.loads(l) for l in p.read_text().splitlines()]
def refs(c):
 a=c['answer'];a=a if isinstance(a,list) else [a]
 expressions=[e for v in a for e in reference_expressions(str(v))]
 # A list of expressions is not a count until duplicate exact values are removed.
 if len(expressions)>1:
  return {json.dumps(describe_exact(e).canonical_key(),sort_keys=True):e for e in expressions}
 return {str(expressions):expressions[0]}
def readcsv(rel):
 p=ROOT/rel;sources.append(p);return list(csv.DictReader(p.open()))
def putcsv(name,rows,fields):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
dev=cases('benchmarks/cases.jsonl');new=cases('jssa/difficulty/new2026/cases.jsonl');unseen=cases('jssa/difficulty/unseen-2/a/cases.jsonl')+cases('jssa/difficulty/unseen-2/b/cases.jsonl')
main=readcsv('jssa/results/mechanism-attribution/attribution.csv')
a=readcsv('jssa/difficulty/unseen-2/a/per-run.csv');b=readcsv('jssa/difficulty/unseen-2/b/results.csv')
assert len(main)==969 and len({(r['case_id'],r['seed']) for r in main})==969
assert {r['case_id'] for r in main}=={c['id'] for c in dev}
assert len(a)==len(b)==85
multi={name:[(c,refs(c)) for c in cs if len(refs(c))>=2] for name,cs in [('development323',dev),('new2026',new),('unseen34',unseen)]}
assert not multi['new2026'] and not multi['unseen34']
byproblem=[];runs=[]
for c,rr in multi['development323']:
 rs=[r for r in main if r['case_id']==c['id']];assert {r['seed'] for r in rs}=={'0','1','2'}
 ct=collections.Counter()
 for r in rs:
  if r['set_relation']=='equal':
   assert r['matched']=='True';label='equal'
  elif r['set_relation']=='missing' and r['status']=='solved':label='nonempty_proper_subset'
  elif r['set_relation']=='missing' and r['status']=='no_answer_found':label='empty'
  else:label='other'
  ct[label]+=1;runs.append({k:r[k] for k in ['case_id','seed','status','matched','set_relation']}|{'posthoc_relation':label})
 byproblem.append(dict(case_id=c['id'],reference_count=len(rr),reference_expressions=json.dumps(list(rr.values()),ensure_ascii=False),equal=ct['equal'],nonempty_proper_subset=ct['nonempty_proper_subset'],empty=ct['empty'],other=ct['other']))
putcsv('multivalue-problems.csv',byproblem,['case_id','reference_count','reference_expressions','equal','nonempty_proper_subset','empty','other'])
putcsv('multivalue-runs.csv',runs,['case_id','seed','status','matched','set_relation','posthoc_relation'])
summary={'unseen34':{'problems':34,'multivalue_problems':0,'source_runs':170,'multivalue_runs':0,'equal':0,'nonempty_proper_subset':0},'new2026':{'problems':20,'multivalue_problems':0,'multivalue_runs':0,'equal':0,'nonempty_proper_subset':0,'full_solver_run_logs':'未確認','found_logs':'jssa/difficulty/new2026-predict/raw/ and logs/ contain single-start local-search measurements, not returned answer sets'},'development323':{'problems':323,'multivalue_problems':len(byproblem),'source_runs':969,'multivalue_runs':len(runs),**dict(collections.Counter(r['posthoc_relation'] for r in runs))},'method':'Frozen reference_expressions handles comma-separated answer strings; describe_exact deduplicates only explicit multi-valued references. Existing set_relation+status read without reassessment. solved/missing is a nonempty proper subset; no_answer_found/missing is empty. Main original returned-value JSONs unavailable; rely on saved per-run labels.'}
(OUT/'multivalue-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(OUT/'count-sources.json').write_text(json.dumps([{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources],indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
