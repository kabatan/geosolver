"""Freeze population, input bytes, sources, reusable seed-0 handoffs, and scripts."""
import csv, hashlib, json, os, platform, shutil, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
S=OUT.parents[1]
REPO=OUT.parents[5]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    data=json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    assert len(data.encode())<3_000_000
    Path(p).write_text(data)
def main():
    assert not (OUT/'pre-run-hashes.json').exists()
    assert shutil.disk_usage('/tmp').free>=6*1024**3
    sources=json.loads((OUT.parent/'source-hashes.json').read_text())
    for key,fileskey in [('base_source','base_files_sha256'),('patched_source','patched_files_sha256'),('frozen_source','frozen_files_sha256')]:
        root=Path(sources[key]); actual={str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
        assert actual==sources[fileskey],key
    sys.path.insert(0,str(Path(sources['patched_source'])/'src'))
    from geosolver.runtime.integrity import source_tree_hash, installed_dependencies, verify_engine_lock
    from geosolver.problem.models import GeometryProblem
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    assert source_tree_hash()==sources['source_hash']
    verify_engine_lock()
    root=Path(tempfile.mkdtemp(prefix='mechanism-S9A-run-'))
    (root/'inputs').mkdir();(root/'runs').mkdir()
    old=json.loads((S/'S1/pre-run-hashes.json').read_text())
    raw=json.loads((S/'S1/raw-hashes.json').read_text())
    s7=json.loads((S/'S7/run2/pre-run-hashes.json').read_text())
    reuse={t['case_id']:t for t in s7['inputs']}
    s1={t['case_id']:t for t in old['inputs']}
    pop=REPO/'jssa/difficulty/mechanism-1024/problem-set/problem-set.json'
    p=json.loads(pop.read_text()); seventy=[c for group in ['hard','fast_algebraic','fast_search','multivalued'] for c in p[group]]
    assert len(seventy)==72
    cases=list(dict.fromkeys([*s1,*seventy])); classified={r['case_id']:r for r in csv.DictReader((S/'S7/classification.csv').open())}
    files=[*sorted(OUT.glob('*.py')),OUT/'rules.md',pop,S/'S1/pre-run-hashes.json',S/'S1/raw-hashes.json',S/'S7/run2/pre-run-hashes.json',S/'S7/classification.csv']
    files += [OUT.parent/n for n in ['design.md','configs.json','switch-r.patch','source-hashes.json','smoke-report.md','audit.py']]
    files += [S/'S1'/n for n in ['prepare.py','driver.py','worker.py','rules.md']]
    files += [S/'S7/run2'/n for n in ['prepare.py','driver.py','worker.py']]
    tasks=[]
    for i,case in enumerate(cases):
        itempath=S/'S7/inputs'/(case+'.json');item=json.loads(itempath.read_text());files.append(itempath)
        origin=Path(s1[case]['input_copy']) if case in s1 else itempath
        dest=root/'inputs'/(case+'.json')
        if case in s1:
            shutil.copyfile(origin,dest);assert sha(dest)==s1[case]['sha256']
            assert json.loads(dest.read_text())==item['dsl']
        else: write(dest,item['dsl'])
        bundle=load_problem_bundle(GeometryProblem.model_validate_json(dest.read_text()).engine_document())
        task=dict(case_id=case,seed=0,input_copy=str(dest),sha256=sha(dest),in_s1=case in s1,in_72=case in seventy,n_variables=len(bundle.var_names),classification=classified[case],reference_expressions=s1[case]['reference_expressions'] if case in s1 else item['reference_expressions'],reference_parse_error=item['reference_parse_error'],arm_order=['R0','R1','R2','R3'][i%4:]+['R0','R1','R2','R3'][:i%4],reuse=None)
        d=root/'runs'/case;d.mkdir()
        prior=None
        if case in s1:
            prior=Path(old['scratch'])/'runs'/case
            for name in ['initial.pkl','initial.json']:
                assert sha(prior/name)==raw[str((prior/name).relative_to(Path(old['scratch'])))]['sha256']
        elif case in reuse:
            pdir=Path(s7['scratch'])/'runs'/case
            if (pdir/'initial.pkl').exists() and (pdir/'initial.json').exists() and (pdir/'search.ended.json').exists():
                ended=json.loads((pdir/'search.ended.json').read_text());j=json.loads((pdir/'initial.json').read_text())
                if ended['returncode']==0 and ended['reason'] is None:
                    assert reuse[case]['sha256']==sha(dest)
                    assert j['seed']==0 and j['source_hash']==sources['base_source_hash']
                    prior=pdir
        if prior:
            for name in ['initial.pkl','initial.json']: shutil.copyfile(prior/name,d/name)
            task['reuse']=dict(origin=str(prior),sha256={name:sha(d/name) for name in ['initial.pkl','initial.json']},provenance='S1 raw-hashes' if case in s1 else 'S7 seed0 BASE handoff and completed search receipt')
        tasks.append(task)
    config=json.loads((OUT.parent/'configs.json').read_text())
    m=dict(created_utc=datetime.now(timezone.utc).isoformat(),scratch=str(root),repository=str(REPO),output=str(OUT),inputs=tasks,
        source_paths={'search':str(Path(sources['base_source'])/'src'),'refine':str(Path(sources['patched_source'])/'src'),'measure':str(Path(sources['frozen_source'])/'src'),'verify':str(Path(sources['frozen_source'])/'src'),'initial':str(Path(sources['frozen_source'])/'src')},
        source_hash=sources['source_hash'],base_source_hash=sources['base_source_hash'],frozen_source_hash=sources['frozen_source_hash'],
        files={str(p):sha(p) for p in files},source_manifest=str(OUT.parent/'source-hashes.json'),
        cpus=sorted(os.sched_getaffinity(0))[-6:],parallel=6,cores=1,seeds=[0],retries=0,
        python=old['python'],python_version=sys.version,dependencies=installed_dependencies(),platform=platform.platform(),host=platform.node(),
        thread_environment={**config['thread_environment'],'BLIS_NUM_THREADS':'1','VECLIB_MAXIMUM_THREADS':'1'},switch_settings=config['arms'],
        seconds={'search':178,'search_outer':180,'refine':90,'refine_outer':98,'initial_outer':90,'measure_outer':90,'verify':90,'verify_outer':98},minimum_free_bytes=6*1024**3)
    write(root/'manifest.json',m);write(OUT/'pre-run-hashes.json',m)
    with (OUT/'progress.md').open('a') as f:f.write(f"# S9A 部分A 進捗\n\n{m['created_utc']} 事前hash固定。和集合{len(tasks)}問、探索変数あり{sum(t['n_variables']>0 for t in tasks)}問、保存候補再利用{sum(t['reuse'] is not None for t in tasks)}問。最大6並列。生データ `{root}`。\n")
    print(json.dumps({'scratch':str(root),'population':len(tasks),'variables':sum(t['n_variables']>0 for t in tasks),'reuse':sum(t['reuse'] is not None for t in tasks)},ensure_ascii=False))
if __name__=='__main__':main()
