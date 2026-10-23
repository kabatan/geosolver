"""Validate report coverage, saved inputs, dimensions and identification evidence."""
import pathlib,json,csv,hashlib,re,subprocess,collections,datetime
O=pathlib.Path(__file__).resolve().parent;ROOT=O.parents[3];U=O.parents[1]/'unseen-2';E=O/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=list(csv.DictReader((O/'audit-34.csv').open()));cases={}
for g in 'ab':
 for r in map(json.loads,(U/g/'cases.jsonl').read_text().splitlines()):cases[r['id']]=(g,r)
assert len(rows)==34 and {r['ID'] for r in rows}==set(cases)
counts=dict(collections.Counter(r['判定'] for r in rows));assert counts=={'原文のみ':26,'要確認':3,'混入あり':5}
inputs=json.loads((E/'audit-inputs.json').read_text());assert len(inputs)==34
for x in inputs:
 assert x['dsl']==cases[x['id']][1]['dsl']
 assert sha(pathlib.Path(x['source_local']))==x['source_sha256']
assert (O/'answer.md').read_text().startswith('事後（結果を見た後の分析）')
existing=list(csv.DictReader((O.parent/'exp1-msolve/per-problem.csv').open()))
ids={r['case_id'] for r in existing if r['msolve_category']=='有限でない'}
expected={'AIME-2005-I-01':1,'AIME-2012-I-14':1,'HMMT-2011-FEB-GUTS-01':2,'HMMT-2019-FEB-GUTS-17':2,'HMMT-2023-FEB-GUTS-03':1}
assert ids==set(expected)
raw=json.loads((O.parent/'exp1-msolve/raw-manifest.json').read_text())['files'];known={r['path']:r for r in raw}
provenance=[]
for id,dim in expected.items():
 p=pathlib.Path('/tmp/q6e1-run/raw/msolve')/id/'in.ms'
 assert sha(p)==known[str(p)]['sha256']
 # Exact saved equations must occur verbatim in our Singular input.
 lines=p.read_text().splitlines();eq='\n'.join(lines[2:]).rstrip(',\n')
 assert eq in (E/(id+'.sing')).read_text()
 log=(E/(id+'.log')).read_text();assert re.search(r'DIM\s+([0-9]+)',log)[1]==str(dim)
 assert not re.search(r'TIMEOUT|error|undefined',log,re.I)
 provenance.append({'path':str(p),'sha256':sha(p),'dimension':dim})
for id,label in [('AIME-2005-I-01','DISTINCT_DIM'),('HMMT-2019-FEB-GUTS-17','NONZERO_S_DIM')]:
 log=(E/(id+'.components.log')).read_text();assert re.search(label+r'\s+([0-9]+)',log)[1]=='0'
 assert not re.search(r'TIMEOUT|error|undefined',log,re.I)
trials=json.loads((E/'identification.json').read_text())['trials'];assert len(trials)==6
for x in trials:
 if x['precision_dps']>=120:assert x['coefficients']==(None if x['max_coeff']==10**8 else [1,0,-27763975108827])
replay=json.loads((E/'direct-replay.json').read_text());diag=replay['diagnostics']
assert replay['status']=='solved' and diag['candidate_records'][0]['candidate_key']['phase']=='direct'
assert diag['pipeline_summary']['search']['evaluation_count']==0
assert diag['pipeline_summary']['exact_assembly']['accepted_count']==1
ind=json.loads((E/'independent.json').read_text());assert ind['AIME-2014-II-10']['official_remainder']==147
for md in O.glob('*.md'):
 for target in re.findall(r'\]\(([^)]+)\)',md.read_text()):
  if '://' in target or '#' in target or target=='validation.json':continue
  assert (md.parent/target).exists(),(md,target)
# Existing tracked source/result files remain unchanged in this checkout.
unchanged=subprocess.check_output(['git','diff','--name-only','--','jssa/difficulty/unseen-2','jssa/difficulty/capability-1024/exp1-msolve'],cwd=ROOT,text=True).strip();assert not unchanged
base_commit='3db2ffb2';source_hashes=[]
for rel in ['answer.md','per-problem.csv','summary.json']:
 p=O.parent/'exp1-msolve'/rel
 committed=subprocess.check_output(['git','show',base_commit+':'+str(p.relative_to(ROOT))],cwd=ROOT)
 assert hashlib.sha256(committed).hexdigest()==sha(p)
 source_hashes.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p),'matches_commit':base_commit})
for rel in ['a/cases.jsonl','b/cases.jsonl','a/per-run.csv','b/results.csv']:
 p=U/rel;source_hashes.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
for id in ['AIME-2012-I-14','AIME-2014-II-10','HMMT-2024-FEB-GUTS-04']:
 g=cases[id][0]
 for seed in range(301,306):
  p=U/g/'execution/runs'/id/(str(seed)+'.json');source_hashes.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
clean=pathlib.Path('/tmp/q6e1-clean');commit=subprocess.check_output(['git','-C',str(clean),'rev-parse','HEAD'],text=True).strip()
assert commit=='60db4b679b04167175c51c479c87c22fa663fda0'
assert not subprocess.check_output(['git','-C',str(clean),'status','--porcelain'],text=True).strip()
frozen=[]
for rel in ['engine/standard/exact_assembly/identify_answer.py','engine/standard/exact_assembly/classify_exact_requirement.py','exact/polynomial_search.py','exact/polynomial_search_helpers.py','runtime/symbolic_operations.py']:
 p=clean/'src/geosolver'/rel;frozen.append({'path':str(p),'sha256':sha(p)})
files=list(O.rglob('*'));files=[p for p in files if p.is_file()];assert max(p.stat().st_size for p in files)<3000000
result={'post_result_analysis':True,'new_hypotheses_or_predictions':False,'audit_rows':34,'audit_counts':counts,'original_statement_unconfirmed':0,'dimensions':expected,'saturated_dimensions':{'AIME-2005-I-01':0,'HMMT-2019-FEB-GUTS-17':0},'saved_polynomial_inputs_match_original_manifest':provenance,'existing_source_records':source_hashes,'frozen_commit':commit,'clean_checkout':True,'frozen_identification_sources':frozen,'identification_only_trials':6,'additional_solver_runs_completed':1,'initial_public_cli_validation_rejection':'5-second budget rejected before solving; accepted 180-second option was externally bounded to 10 seconds','existing_tracked_inputs_and_scores_unchanged':True,'largest_artifact_bytes':max(p.stat().st_size for p in files),'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(O/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['saved_polynomial_inputs_match_original_manifest','existing_source_records','frozen_identification_sources']},ensure_ascii=False,indent=2))
