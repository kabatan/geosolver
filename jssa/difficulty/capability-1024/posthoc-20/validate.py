"""Validate the posthoc artifacts without rerunning solvers or reassessing logs."""
import pathlib,json,subprocess,hashlib,csv,re,os,resource,datetime,sys
OUT=pathlib.Path(__file__).resolve().parent;ROOT=OUT.parents[3];CLEAN=pathlib.Path('/tmp/posthoc20-clean')
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_CPU,(12,12))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert (OUT/'answer.md').read_text().startswith('事後（結果を見た後の分析）。凍結版の主結果とは別')
commit=subprocess.check_output(['git','-C',str(CLEAN),'rev-parse','HEAD'],text=True).strip()
assert commit=='60db4b679b04167175c51c479c87c22fa663fda0'
assert not subprocess.check_output(['git','-C',str(CLEAN),'status','--porcelain'],text=True).strip()
protected=['jssa/difficulty/capability-1024/exp1-msolve','jssa/difficulty/capability-1024/examples','jssa/difficulty/capability-1024/preregistration-6.md','jssa/difficulty/unseen-2/a/cases.jsonl','jssa/difficulty/unseen-2/b/cases.jsonl','jssa/difficulty/unseen-2/a/per-run.csv','jssa/difficulty/unseen-2/b/results.csv','benchmarks/cases.jsonl','jssa/results/mechanism-attribution/attribution.csv','jssa/difficulty/new2026/cases.jsonl','src']
assert not subprocess.check_output(['git','diff','HEAD','--name-only','--',*protected],cwd=ROOT,text=True).strip()
pre=json.loads((ROOT/'jssa/difficulty/capability-1024/exp1-msolve/preflight.json').read_text())
conv=pathlib.Path('/tmp/q6-tools/exact_comparison/benchmarks/exact_comparison')
for name,h in pre['exact_code_sha256'].items():assert sha(conv/name)==h
assert sha(ROOT/'jssa/difficulty/capability-1024/preregistration-6.md')==pre['preregistration_sha256']
for r in json.loads((OUT/'count-sources.json').read_text()):assert sha(ROOT/r['path'])==r['sha256']
rows=list(csv.DictReader((OUT/'multivalue-runs.csv').open()));assert len(rows)==24
assert {k:sum(r['posthoc_relation']==k for r in rows) for k in ['equal','nonempty_proper_subset','empty']}=={'equal':17,'nonempty_proper_subset':4,'empty':3}
problem=list(csv.DictReader((OUT/'multivalue-problems.csv').open()));assert len(problem)==8
summary=json.loads((OUT/'multivalue-summary.json').read_text());assert summary['unseen34']['multivalue_problems']==summary['new2026']['multivalue_problems']==0
comparisons=json.loads((OUT/'comparison.json').read_text());assert len(comparisons)==5
for r in comparisons:
 assert sha(OUT/'evidence'/f"{r['id']}.sing")==r['input_sha256']
 assert r['wall_seconds']<21
 if r['id']=='HMMT-2019-FEB-GUTS-17':assert r['returncode']=='timeout' and 'SAT_DONE' not in r['log']
 else:assert r['returncode']==0 and r['real_roots']
verification=[]
for p in sorted((OUT/'evidence').glob('*.verification.json')):
 d=json.loads(p.read_text());r=d['result'];assert r['verified'] and r['hard_feasible'] and not r['hard_failure_tags']
 assert float(r['normalized_residual'])<1e-30
 verification.append({'id':d['id'],'verified':True,'precision_dps':r['precision_dps'],'normalized_residual':r['normalized_residual']})
assert len(verification)==4
reuse=json.loads((OUT/'reuse-saturation.json').read_text());assert reuse['returncode']==0 and reuse['target_scale']==4 and not reuse['answer_set_verified']
assert sha(ROOT/reuse['saturation_source'])==reuse['saturation_source_sha256']
assert reuse['reference_remainder']=='0' and reuse['elimination_degree']==62
# Check target scaling and membership from saved bytes, not a solver invocation.
sys.path[:0]=[str(CLEAN/'src'),str(CLEAN),str(conv)]
import sympy as sp
from algebraize import translate
from run_exact import build,poly_str
c=next(c for c in map(json.loads,(ROOT/'jssa/difficulty/unseen-2/b/cases.jsonl').read_text().splitlines()) if c['id']=='HMMT-2019-FEB-GUTS-17')
s,unused=translate(c['dsl'],mode='fresh',with_target=False);eqs,used,_=build(s,True);ren={v:sp.Symbol(f'x{i}') for i,v in enumerate(used)}
raw=pathlib.Path('/tmp/q6e1-run/raw/msolve/HMMT-2019-FEB-GUTS-17/in.ms').read_text().splitlines()
normalize=lambda x:re.sub(r'\s+','',x)
assert normalize(','.join(poly_str(e.xreplace(ren)) for e in eqs))==normalize(''.join(raw[2:]))
assert {str(v):str(ren[v]) for v in used}==reuse['variable_mapping']
T=sp.Symbol('T');P=sp.Poly(sp.sympify(re.search(r'ELIM_BEGIN\s*\n(.*?)ELIM_END',reuse['log'],re.S)[1].strip().replace('^','**')),T)
assert P.degree()==62 and P.rem(sp.Poly(900*T*T-360*T-327,T)).is_zero
# Match original saved inputs to their historical manifest.
manifest=json.loads((ROOT/'jssa/difficulty/capability-1024/exp1-msolve/raw-manifest.json').read_text())['files'];known={x['path']:x for x in manifest}
for cid in ['AIME-2005-I-01','HMMT-2019-FEB-GUTS-17']:
 p=pathlib.Path('/tmp/q6e1-run/raw/msolve')/cid/'in.ms';assert sha(p)==known[str(p)]['sha256']
for p in OUT.glob('*.md'):
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  if '://' not in target and not target.startswith('#') and target!='validation.json':assert (p.parent/target.split('#')[0]).exists(),target
files=[p for p in OUT.rglob('*') if p.is_file()];assert max(p.stat().st_size for p in files)<3_000_000
sources=json.loads((OUT/'count-sources.json').read_text())
for rel in ['jssa/difficulty/capability-1024/exp1-msolve/answer.md','jssa/difficulty/capability-1024/exp1-msolve/per-problem.csv','jssa/difficulty/capability-1024/preregistration-6.md']:
 sources.append({'path':rel,'sha256':sha(ROOT/rel)})
result={'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'post_result_analysis':True,'new_hypotheses_or_predictions':False,'frozen_commit':commit,'clean_checkout':str(CLEAN),'clean_checkout_unchanged':True,'protected_tracked_sources_match_HEAD':protected,'converter_matches_historical_preflight':pre['exact_code_sha256'],'sources':sources,'final_verifications':verification,'singular_executions':6,'full_geosolver_search_executions':0,'h2019_initial_timeout_seconds':comparisons[3]['wall_seconds'],'h2019_reuse_saturation_previous_computation_time_excluded':True,'h2019_reuse_target':'T=Area/4; primitive shoelace polynomial has scale 4','h2019_reuse_polynomial_degree':62,'h2019_reuse_reference_is_only_candidate':True,'h2019_reuse_all_candidates_filtered':False,'pre_execution_import_error':'reuse_saturation.py initially imported a script that accessed sys.argv[1]; fixed main guards before its first Singular invocation','multivalue_counts':summary,'largest_artifact_bytes':max(p.stat().st_size for p in files),'artifact_bytes_total_before_validation':sum(p.stat().st_size for p in files),'system_install':False,'git_commit_or_push':False}
(OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
assert (OUT/'validation.json').stat().st_size<3_000_000
print(json.dumps({'clean_checkout':True,'converter_unchanged':True,'existing_inputs_and_scores_unchanged':True,'verifications':len(verification),'singular_runs':6,'multiple_problems':8,'equal':17,'partial':4,'empty':3,'largest_file_bytes':result['largest_artifact_bytes']},ensure_ascii=False))
