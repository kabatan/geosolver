"""Audit completeness, immutable inputs, numerical consistency and final hashes."""
from common import *
from mpmath import mp
from measure import spectrum,kind

def main():
    manifest=check_manifest()
    expected=set(manifest['case_ids'])
    files=sorted((OUT/'results').glob('*.json'))
    assert {p.stem for p in files}==expected
    with (OUT/'per-problem.csv').open() as f: rows=list(csv.DictReader(f))
    assert {r['case_id'] for r in rows}==expected and len(rows)==len(expected)
    w3=set(manifest['protocol']['w3'])
    max_central_error=mp.mpf(0)
    count=0
    with mp.workdps(200):
        for p in files:
            r=load(p)
            assert r['status']=='ok' and not r['stage_2_executed']
            assert r['pre_run_manifest_sha256']==sha(OUT/'pre-run-hashes.json')
            assert r['base_type_count']==len(r['inventory']['base_types'])
            assert len(r['samples'])==2
            for accessed,digest in r['accessed_files'].items():assert sha(accessed)==digest
            for s in r['samples']:
                jp=mp.matrix([[mp.mpf(x) for x in row] for row in s['jacobian_plus']])
                jm=mp.matrix([[mp.mpf(x) for x in row] for row in s['jacobian_minus']])
                jc=mp.matrix([[mp.mpf(x) for x in row] for row in s['jacobian_central']])
                assert (jp.rows,jp.cols)==(r['m_raw'],r['n'])
                assert mp.norm(jc-(jp+jm)/2)/max(1,mp.norm(jc))<mp.mpf('1e-190')
                gap=mp.norm(jp-jm)/max(1,mp.norm(jp),mp.norm(jm))
                assert abs(gap-mp.mpf(s['normalized_matrix_gap']))<mp.mpf('1e-190')*max(1,gap)
                max_central_error=max(max_central_error,mp.mpf(s['stage1_central_relative_error']))
                for side,j in [('plus',jp),('minus',jm),('central',jc)]:
                    data=s[side]
                    assert len(data['singular_values'])==r['n']
                    assert mp.mpf(data['svd_reconstruction_error'])<mp.mpf('1e-170')
                    assert data['classification']==kind(mp.mpf(data['sigma']))
                a,b=mp.mpf(s['plus']['sigma']),mp.mpf(s['minus']['sigma'])
                judgment='微分不能' if a>mp.mpf('1e-10') or b>mp.mpf('1e-10') or gap>mp.mpf('1e-20') else ('特異' if a<mp.mpf('1e-60') and b<mp.mpf('1e-60') else '不定')
                assert judgment==s['classification']
                if r['case_id'] in w3:
                    assert s['base']['classification']=='非特異'
                    assert len(s['single_condition_reversions'])==len(r['inventory']['changes'])
                count+=1
            cs=[s['classification'] for s in r['samples']]
            assert r['classification']==(cs[0] if cs[0]==cs[1] else '不定')
    execution=load(OUT/'execution.json');assert execution['parallel_max']<=4 and execution['cases']==len(expected)
    save(OUT/'verification.json',dict(status='ok',cases=len(expected),width_samples=count,immutable_input_hashes_checked=True,
          all_accessed_source_and_stage1_hashes_checked=True,central_matches_stage1_below='1e-120',
          maximum_central_relative_error=mp.nstr(max_central_error,20,min_fixed=0,max_fixed=0),
          one_sided_matrix_identity_checked=True,classification_recomputed=True,svd_reconstruction_error_below='1e-170',
          all_w3_condition_reversions_present=True,parallel_max=execution['parallel_max'],stage_2_executed=False))
    hashes=[(p.relative_to(OUT).as_posix(),sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='hashes.sha256' and '__pycache__' not in p.parts]
    (OUT/'hashes.sha256').write_text(''.join(d+'  '+name+'\n' for name,d in hashes))
    print(json.dumps(load(OUT/'verification.json'),ensure_ascii=False))

if __name__=='__main__':main()
