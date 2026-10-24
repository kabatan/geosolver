"""Read-only verification, except the small verification receipt. No solver/CAS."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import statistics

from collect_real import features, SOURCES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    checks = []
    rows = list(csv.DictReader((HERE/'real-problems.csv').open()))
    assert Counter(r['group'] for r in rows) == {'dev323':323, 'unseen34':34}
    assert len({r['problem_id'] for r in rows}) == 357
    extra={'solver_missing_count','solver_recorded_count','solver_confirmed_noncorrect_count','solver_missing_seeds'}
    fields=[k for k in rows[0] if k not in extra]
    buffer=io.StringIO()
    writer=csv.DictWriter(buffer,fieldnames=fields)
    writer.writeheader()
    writer.writerows({k:r[k] for k in fields} for r in rows)
    first=json.loads((HERE/'real-table-milestone.json').read_text())
    assert hashlib.sha256(buffer.getvalue().encode()).hexdigest()==first['table_sha256']
    checks.append('all first-delivered table values unchanged; only explicit missing-run columns added')
    cases = {}
    for group, path in SOURCES:
        for line in (ROOT/path).read_text().splitlines():
            case=json.loads(line)
            cases[group,case['id']]=case
    assert {(r['group'],r['problem_id']) for r in rows} == set(cases)
    checks.append('all 357 expected IDs and groups, no duplicate/missing rows')
    source_cache = {}
    n_degree, n_scripts = 0, 0
    for r in rows:
        f,_=features(cases[r['group'],r['problem_id']]['dsl'])
        for key,value in f.items():
            assert int(r[key])==value, (r['problem_id'],key)
        source=r['solver_source']
        if source not in source_cache:
            result=defaultdict(list)
            for s in csv.DictReader((ROOT/source).open()):
                result[s['case_id']].append(s)
            source_cache[source]=result
        samples=source_cache[source][r['problem_id']]
        success=[float(s[r['solver_time_column']]) for s in samples if s['matched']=='True']
        assert len(success)==int(r['solver_correct'])
        assert len(samples)==int(r['solver_runs'])
        assert r['solver_correct_seconds_median']=='' if not success else abs(
            float(r['solver_correct_seconds_median'])-statistics.median(success))<1e-10
        missing=sum(s.get('record_missing',s.get('missing_record','False'))=='True' for s in samples)
        assert missing==int(r['solver_missing_count'])
        assert len(samples)==int(r['solver_correct'])+missing+int(r['solver_confirmed_noncorrect_count'])
        combined_cas=0
        for mode in ['base','strong']:
            rec=json.loads((HERE/'records'/r['group']/f'{r["problem_id"]}.{mode}.json').read_text())
            assert r[mode+'_status']==rec['status']
            assert r[mode+'_status'] not in ['PENDING','CAS_RUNNING']
            assert float(rec.get('cas_limit_s',0)) <= 30
            combined_cas+=float(rec.get('cas_wall_s',0))
            if 'degree' in rec:
                n_degree+=1
                assert int(r[mode+'_degree'])==rec['degree']
                assert int(r[mode+'_dimension'])==rec['dimension']
                if rec['nvars']:
                    log=(HERE/'records'/r['group']/f'{r["problem_id"]}.{mode}.log').read_text()
                    assert not re.search(r'^\s*\?',log,re.M), (r['problem_id'],mode,log)
                    for label,key in [('DIM','dimension'),('DEG','degree')]:
                        assert int(re.search(r'^'+label+r'=(-?\d+)\s*$',log,re.M)[1])==rec[key]
                    if rec['dimension']==0:
                        assert int(re.search(r'^VDIM=(-?\d+)\s*$',log,re.M)[1])==rec['degree']
                    if mode=='strong':
                        factors=re.findall(r'^SAT_FACTOR=\d+\s*$',log,re.M)
                        assert len(factors)==rec['nonzero_factors']
            else:
                assert r[mode+'_degree']=='' and r[mode+'_degree_label']=='次数不明'
            if 'script_sha256' in rec:
                path=HERE/'records'/r['group']/f'{r["problem_id"]}.{mode}.sing'
                assert hashlib.sha256(path.read_bytes()).hexdigest()==rec['script_sha256']
                n_scripts+=1
        # Popen polling adds a small wall-clock overhead after a 30s deadline.
        assert combined_cas < 61, (r['problem_id'],combined_cas)
    checks += ['all depths recomputed from AST', 'historic solver counts/medians and missing seeds match source',
               f'{n_degree} computed degree/dimension records agree with CSV and Singular logs',
               f'{n_scripts} Singular input hashes agree; successful strong saturations completed',
               'all per-problem two-CAS nominal limits <= 60 seconds']
    manifest=json.loads((HERE/'provenance.json').read_text())
    for entry in manifest['files']:
        path=Path(entry['path'])
        if not path.is_absolute(): path=ROOT/path
        assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256'],path
    checks.append('all source data and unchanged translators match initial SHA-256')
    events=[json.loads(l) for l in (HERE/'progress.jsonl').read_text().splitlines()]
    complete=next(e for e in events if e['event']=='実問題表完了')
    if (HERE/'family-progress.jsonl').exists():
        families=[json.loads(l) for l in (HERE/'family-progress.jsonl').read_text().splitlines()]
        assert all(e['utc'] >= complete['utc'] for e in families)
        checks.append('family work started after real table completion receipt')
    family_rows=[]
    elimination_checks=0
    if (HERE/'degrees.csv').exists():
        import sympy as sp
        T=sp.Symbol('T')
        family_rows=list(csv.DictReader((HERE/'degrees.csv').open()))
        assert Counter(r['family'] for r in family_rows)=={
            'circle_line':8,'angle_bisector':8,'midpoint_control':8}
        for r in family_rows:
            k=int(r['k'])
            expected=1 if r['family']=='midpoint_control' else 2**k
            dsl=json.loads((HERE/r['dsl_path']).read_text())
            f,_=features(dsl)
            assert f['depth']==f['point_depth']==k
            assert len(dsl['variables'])==1
            cert=json.loads((HERE/r['t_minimal_polynomial_path']).read_text())
            target_poly=sp.Poly(sp.sympify(cert['minimal_polynomial'],locals={'T':T}),T,domain=sp.QQ)
            assert cert['degree']==target_poly.degree()==expected==int(r['t_minimal_polynomial_degree'])
            assert [str(c) for c in target_poly.all_coeffs()]==cert['coefficients']
            if r['family']=='circle_line':
                coeff=[int(c) for c in target_poly.all_coeffs()]
                assert all(c%2==0 for c in coeff[1:]) and coeff[-1]%4==2 and coeff[0]%2==1
            elif r['family']=='angle_bisector':
                n=2**k
                expression=sum(sp.binomial(n,j)*(-1)**(j//2)*(1 if j%2==0 else -1)*T**j for j in range(n+1))
                assert sp.Poly(expression,T,domain=sp.QQ).monic()==target_poly.monic()
                assert all(int(sp.binomial(2*n,j))%2==0 for j in range(1,2*n))
            else:
                assert target_poly.as_expr()==2**k*T-1
            for mode in ['base','strong']:
                directory=HERE/'families'/r['family']
                rec=json.loads((directory/f'k{k}.{mode}.json').read_text())
                assert rec['degree']==int(r[mode+'_degree'])==expected
                assert rec['dimension']==int(r[mode+'_dimension'])==0
                assert rec['status']==r[mode+'_status']=='OK_ZERO_DIMENSIONAL'
                assert hashlib.sha256((directory/f'k{k}.{mode}.sing').read_bytes()).hexdigest()==rec['script_sha256']
                log=(directory/f'k{k}.{mode}.log').read_text()
                assert not re.search(r'^\s*\?',log,re.M)
                assert int(re.search(r'^DEG=(-?\d+)\s*$',log,re.M)[1])==expected
                assert int(re.search(r'^VDIM=(-?\d+)\s*$',log,re.M)[1])==expected
                if mode=='strong':
                    assert len(re.findall(r'^SAT_FACTOR=\d+\s*$',log,re.M))==rec['nonzero_factors']
                    if rec.get('elimination_polynomials'):
                        var=sp.Symbol(rec['target_singular_variable'])
                        polys=[sp.Poly(sp.sympify(p.replace('^','**'),locals={str(var):var}),var,domain=sp.QQ)
                               for p in rec['elimination_polynomials'] if p!='0']
                        gcd=polys[0]
                        for poly in polys[1:]:gcd=sp.gcd(gcd,poly)
                        obtained=sp.Poly(gcd.sqf_part().monic().as_expr().subs(var,T),T,domain=sp.QQ)
                        assert obtained==target_poly.monic()
                        assert r['t_elimination_check']=='MATCHES_PROVED_MINIMAL_POLYNOMIAL'
                        elimination_checks+=1
                    else:
                        assert (r['family'],k)==('angle_bisector',8)
                        assert r['t_elimination_check']=='ELIMINATION_TIMEOUT'
        assert elimination_checks==23
        checks += ['24 family DSLs have exact requested depth and one free scalar',
                   '48 family degree/dimension outputs match CSV; 24 target-degree proof certificates checked',
                   '23 target eliminations match proved minimal polynomials; angle k=8 elimination timeout preserved']
    large=[str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file() and p.stat().st_size>3_000_000]
    assert not large,large
    checks.append('every artifact below 3,000,000 bytes')
    report=dict(utc=datetime.now(timezone.utc).isoformat(),status='PASS',checks=checks,
                n_real_rows=len(rows),degree_records=n_degree,
                existing_solver_and_converter_changes=False,new_geosolver_runs=0,new_timing_comparison_runs=0,
                family_rows=len(family_rows),family_target_elimination_checks=elimination_checks,
                complete_table_utc=complete['utc'])
    (HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
