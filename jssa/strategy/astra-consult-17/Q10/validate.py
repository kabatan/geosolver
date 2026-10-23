"""Final semantic checks on artifacts; no rerun or altered experimental result."""
from pathlib import Path
import json,csv,hashlib,re,ast,sys,copy,datetime,platform,os
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'vendor'))
from verify_certificate import verify
from fractions import Fraction
def main():
    files=[p for p in HERE.rglob('*') if p.is_file()]
    for p in files:
        assert p.stat().st_size<16*1024**2,p
        if p.suffix=='.json':json.loads(p.read_text())
        if p.suffix=='.py':ast.parse(p.read_text(),filename=str(p))
    lock=json.loads((HERE/'registration-lock.json').read_text())
    assert hashlib.sha256((HERE/'preregistration.md').read_bytes()).hexdigest()==lock['preregistration_sha256']
    manifest={r['id']:r['sha256'] for r in json.loads((HERE/'input-manifest.json').read_text())}
    cases=[];chart_count=0;fresh_count=0
    for cid in lock['ids']:
        inp=HERE/'inputs'/f'{cid}.json';assert set(json.loads(inp.read_text()))=={'id','dsl'}
        assert hashlib.sha256(inp.read_bytes()).hexdigest()==manifest[cid]
        for arm in ['A','B']:
            d=HERE/'runs'/f'{cid}__{arm}';r=json.loads((d/'result.json').read_text())
            assert r['status']!='running' and r['input_sha256']==manifest[cid]
            for p in d.glob('certificate*.json'):
                c=json.loads(p.read_text());assert verify(c);fresh_count+=1
        cpath=HERE/'audit/charts'/f'{cid}.json'
        if cpath.exists():
            c=json.loads(cpath.read_text());assert verify(c) and c['root_check']['unique'];chart_count+=1
            altered=copy.deepcopy(c);altered['Q'].append([[0]*len(c['variables']),'1'])
            # merge a constant term, rather than relying on duplicate-entry behavior
            sums={}
            for m,v in altered['Q']:sums[tuple(m)]=sums.get(tuple(m),Fraction(0))+Fraction(v)
            altered['Q']=[[list(m),str(v)] for m,v in sums.items() if v]
            assert not verify(altered)
        diag=json.loads((HERE/'diagnostic'/cid/'result.json').read_text());assert diag['status']!='running'
    assert fresh_count==15 and chart_count==15
    ce=json.loads((HERE/'audit/JMO-2014-PRE-09-counterexample.json').read_text())
    assert {w['target'] for w in ce['witnesses']}=={1,2}
    assert all(w['all_exact_constraints'] and w['hp_hard_feasible'] and float(w['hp_residual_max'])<1e-90 for w in ce['witnesses'])
    links=[]
    for p in HERE.glob('*.md'):
        for url in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' in url or url.startswith('#'):continue
            path=url.split('#')[0]
            assert (p.parent/path).exists(),(p,url)
            links.append(str(p.name)+':'+url)
    source_hashes={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.suffix=='.py'}
    diagrows=[json.loads(p.read_text()) for p in (HERE/'diagnostic').glob('*/result.json')]
    with (HERE/'diagnostic-summary.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['id','status','seconds','E','roots']);w.writeheader()
        for r in sorted(diagrows,key=lambda d:d['id']):w.writerow({k:r.get(k,'') for k in w.fieldnames})
    # A machine-readable 16-row real-branch verdict, independent of automatic success.
    rows=[]
    old={r['id']:r for r in csv.DictReader((HERE/'audit_source/prior-batch-summary.csv').open())}
    for cid in lock['ids']:
        path=HERE/'audit/charts'/f'{cid}.json'
        c=json.loads(path.read_text()) if path.exists() else {}
        rows.append(dict(id=cid,prior_status=old.get(cid,{}).get('status','outside_old_63'),
          real_DSL_verdict='conditional_unique_value_with_human_reduction' if c else 'nonunique_real_DSL_component',
          Q=c.get('Q_expression','no nonzero target-only polynomial can cover the continuum'),
          evidence=str(path.relative_to(HERE)) if c else 'audit/JMO-2014-PRE-09-counterexample.json',
          original_statement_rechecked=False))
    with (HERE/'root-audit.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    sources=list(json.loads((HERE/'provenance.json').read_text()))
    assert all(hashlib.sha256((HERE/r['destination']).read_bytes()).hexdigest()==r['sha256'] for r in sources)
    import sympy,scipy,mpmath,numpy
    result=dict(valid=True,preregistration_hash_unchanged=True,inputs=16,main_trials=32,diagnostic_trials=16,
      exact_fresh_certificates=fresh_count,exact_real_chart_certificates=chart_count,wrong_chart_Q_rejected=chart_count,
      jmo_exact_counterexamples=2,local_links_checked=len(links),python_sources_parsed=len(source_hashes),
      code_sha256=source_hashes,versions={m.__name__:m.__version__ for m in [sympy,scipy,mpmath,numpy]},
      platform=platform.platform(),affinity_count=len(os.sched_getaffinity(0)),max_compute_workers=4,
      total_bytes=sum(p.stat().st_size for p in files),largest_bytes=max(p.stat().st_size for p in files),
      validation_timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (HERE/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='code_sha256'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
