import csv,hashlib,json,os,pathlib,shutil,subprocess,sys,platform
from datetime import datetime,timezone
root=pathlib.Path.cwd(); clean=pathlib.Path('/tmp/q6e1-clean'); run=pathlib.Path('/tmp/q6e1-run'); out=root/'jssa/difficulty/capability-1024/exp1-msolve'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(clean),*args]).decode().strip()
assert git('rev-parse','HEAD').startswith('60db4b6')
assert not git('status','--porcelain')
sys.path.insert(0,str(clean/'src'))
import geosolver
from geosolver.runtime.integrity import source_tree_hash,verify_engine_lock,installed_dependencies
actual=source_tree_hash(); assert actual=='sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'; assert verify_engine_lock()[0]
files=git('ls-tree','-r','--name-only','HEAD','src').splitlines()
for f in files:assert (clean/f).read_bytes()==subprocess.check_output(['git','-C',str(clean),'show','HEAD:'+f])
(run/'benchmarks').mkdir(parents=True,exist_ok=True)
shutil.copytree('/tmp/q6-tools/exact_comparison/benchmarks/exact_comparison',run/'benchmarks/exact_comparison',dirs_exist_ok=True)
shutil.copyfile(clean/'benchmarks/research_runner.py',run/'benchmarks/research_runner.py')
cases=[]; inputs={}; geo={}
for group in ('a','b'):
 base=root/'jssa/difficulty/unseen-2'/group; lock=json.loads((base/'prediction.lock.json').read_text())
 assert sha(base/'cases.jsonl')==lock.get('artifacts_sha256',lock.get('artifact_sha256'))['cases.jsonl']
 cc=[json.loads(s) for s in (base/'cases.jsonl').read_text().splitlines()]; assert len(cc)==17
 for c in cc:
  p=base/c['dsl_path']; assert json.loads(p.read_text())==c['dsl']
 cases+=cc
 inputs[str((base/'cases.jsonl').relative_to(root))]=sha(base/'cases.jsonl')
 table=base/('per-run.csv' if group=='a' else 'results.csv')
 rows=list(csv.DictReader(table.open())); assert len(rows)==85
 for c in cc:
  rr=[r for r in rows if r['case_id']==c['id']]; assert sorted(int(r['seed']) for r in rr)==list(range(301,306))
 inputs[str(table.relative_to(root))]=sha(table)
 geo[group]={'path':str(table.relative_to(root)),'runs':len(rows)}
assert len({c['id'] for c in cases})==34
(run/'benchmarks/cases.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cases))
(run/'ids.txt').write_text(''.join(c['id']+'\n' for c in cases))
prepared=pathlib.Path('/tmp/q6-tools/exact_comparison/benchmarks/exact_comparison')
codehash={p.name:sha(p) for p in prepared.iterdir() if p.is_file()}
for n,h in codehash.items():assert sha(run/'benchmarks/exact_comparison'/n)==h
prereg=root/'jssa/difficulty/capability-1024/preregistration-6.md'
assert prereg.read_bytes()==subprocess.check_output(['git','show','70443d65:'+str(prereg.relative_to(root))])
manifest={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'authorization':'User stage 2 authorized; predictions/thresholds/targets fixed before execution','preregistration_commit':'70443d65e5db5375959777216cd05bf7c2626f89','preregistration_sha256':sha(prereg),'preregistration_push':'User reports pushed UTC 2026-10-23T18:06:13Z; local remote-tracking ref contains commit','frozen_commit':git('rev-parse','HEAD'),'clean_checkout':str(clean),'clean_tracked_status':git('status','--porcelain'),'source_hash':actual,'source_files_verified_against_git':len(files),'import_root':geosolver.__file__,'python':sys.executable,'dependencies':installed_dependencies(),'exact_code_sha256':codehash,'exact_code_origin':'Prepared copy of claude/project-thread-fos2rk; no code edits','run_code_location':str(run/'benchmarks/exact_comparison'),'research_runner_sha256':sha(clean/'benchmarks/research_runner.py'),'cases':len(cases),'input_sha256':inputs,'comparison_tables':geo,'msolve_version':'0.9.4','singular_version':'4.4.1','solver_timeout_seconds':600,'memory_address_space_bytes':8*(1<<30),'parallel_jobs':4,'solver_threads':1,'translation_mode':'fresh','filter_timeout_seconds':600,'positive_dimension_policy':'Run unchanged run_exact.py elim with Singular; candidate superset is not a verified correct answer set','e2_policy':'No answer due to timeout/memory/nonfinite/unsupported; wrong verified finite answer sets excluded','e3_policy':'Intersection of exact answer-set matches and >=1/5 GeoSolver correct; compare median solver solve_seconds and median of per-problem GeoSolver successful wall_seconds medians. Report total exact time separately. Shared host and four parallel jobs, historical load differs.','raw_directory':str(run/'raw'),'load_before':os.getloadavg(),'hostname':platform.node(),'affinity':sorted(os.sched_getaffinity(0))}
(out/'preflight.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'source_hash':actual,'cases':len(cases),'code_files':len(codehash),'clean':not git('status','--porcelain'),'geosolver_import':geosolver.__file__},ensure_ascii=False))
