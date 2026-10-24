"""Verify S7 provenance, reference gates and stored measurement consistency only."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from mpmath import mp
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def kind(v): return '特異' if v<mp.mpf('1e-60') else ('非特異' if v>mp.mpf('1e-10') else '不定')
def main():
    assert len(M['items'])==323
    assert M['parallel']<=8 and M['solve_retries']==0 and M['solve_seed']==0
    for p,s in {**M['files'],**M['source_files']}.items(): assert sha(p)==s,p
    rows=[];events=[];references=0;solves=0;missing_tangency=[]
    with mp.workdps(200):
        for t in M['items']:
            folder=OUT/'results'/t['case_id'];row=read(folder/'result.json');rows.append(row)
            assert row['stage_2_executed'] is False
            start=read(folder/'started.json')['started']
            events.extend([(start,1),(start+row['elapsed_seconds'],-1)])
            if (folder/'solve-started.json').exists():
                s=read(folder/'solve-started.json');solves+=1
                assert s['seed']==0 and s['time_limit_seconds']==180 and s['source_hash']==M['source_hash']
            if row['status']=='excluded_no_variables': assert row['n_variables']==0
            else: assert row['n_variables']>0
            if row.get('reference_status')=='ok':
                ref=read(folder/'reference.json');references+=1
                assert ref['status']=='ok' and ref['hard_feasible']
                assert ref['verification']['verified'] and ref['refinement_dps']==620
                assert mp.mpf(ref['original_residual_norm'])<=mp.mpf('1e-580')
                assert mp.mpf(ref['absolute_error'])<=mp.mpf('1e-300')
                assert mp.mpf(ref['relative_error'])<=mp.mpf('1e-300')
            if row['status']=='ok':
                d=read(folder/'sigma-details.json')
                assert len(d['var_names'])==row['n_variables'] and bool(d['tangencies'])==row['has_tangency']
                for mode in ('base','raw'):
                    samples=d['modes'][mode]['samples']
                    assert [s['step_exponent'] for s in samples]==[70,60]
                    for s in samples:
                        assert len(s['singular_values'])==row['n_variables']
                        assert len(s['jacobian'])==len(d['layouts'][mode])==row[mode+'_rows']
                        assert all(len(v)==row['n_variables'] for v in s['jacobian'])
                        assert all(mp.isfinite(mp.mpf(v)) and mp.mpf(v)>=0 for v in s['singular_values'])
                        assert mp.mpf(s['svd_reconstruction_error'])<mp.mpf('1e-170')
                    assert samples[0]['singular_values'][0]==row['sigma_'+mode]
                    assert samples[1]['singular_values'][0]==row['sigma_'+mode+'_check']
                    ks=[kind(mp.mpf(s['singular_values'][0])) for s in samples]
                    assert row[mode+'_judgment']==(ks[0] if ks[0]==ks[1] else '不定')
                assert row['W3_target']==(row['raw_judgment']=='特異' and row['base_judgment']=='非特異' and not row['has_tangency'])
            item=read(t['input'])
            if 'IsTangent(' in json.dumps(item['dsl']['conditions']) and not row.get('has_tangency'): missing_tangency.append(row['case_id'])
    active=maximum=0
    for _,change in sorted(events):
        active+=change;maximum=max(maximum,active)
    assert maximum<=8 and active==0
    assert not missing_tangency,missing_tangency
    files=[p for p in OUT.rglob('*') if p.is_file()]
    assert all(p.stat().st_size<3_000_000 for p in files)
    summary=dict(status='passed',stage_2_executed=False,input_count=323,status_counts=dict(Counter(r['status'] for r in rows)),reference_gates_passed=references,ordinary_solve_receipts=solves,maximum_concurrent_workers_from_receipts=maximum,per_file_limit_bytes=3_000_000,max_file_bytes=max(p.stat().st_size for p in files),pre_run_hashes_unchanged=True,all_stored_sigma_classifications_verified=True,all_stored_svd_reconstruction_errors_below_1e_minus_170=True,explicit_IsTangent_coverage_complete=True)
    (OUT/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
