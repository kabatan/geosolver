"""Independent structural/numeric audit of Q34 delivered records (no searches)."""
from collections import Counter
import csv
import hashlib
import gzip
import json
from pathlib import Path
import subprocess
import sys
import dataio
from experiment import ROOT, OUT, IDS, EPS, MODES, SUPPLEMENT_MODES, check_lock, sha, save, utc
import numpy as np

def audit():
    check_lock()
    inputs=json.loads((OUT/'inputs.json').read_text())
    frozen={c['id']:c for c in map(json.loads,subprocess.check_output(
        ['git','show','60db4b6:benchmarks/cases.jsonl'],cwd=ROOT,text=True).splitlines())}
    assert all(frozen[i['id']]['dsl']==i['dsl'] for i in inputs)
    assert not subprocess.check_output(['git','diff','60db4b6','--','src'],cwd=ROOT)
    checks=[];local_calls=0;local_seconds=0;classes=Counter();capchanges=0;repeats=0
    curve={(r['id'],float(r['epsilon'])):r for r in csv.DictReader((OUT/'uncertainty.csv').open())}
    examples=[];poly=[];ulp_changes=0;ulp_root_changes=0;ulp_target_changes=0
    for inp in inputs:
        cid=inp['id'];rows=[]
        for p in sorted((OUT/'measure').glob(cid+'-*.json')):rows+=json.loads(p.read_text())['rows']
        assert sorted(r['i'] for r in rows)==list(range(256)),cid
        width=np.diff(np.asarray(inp['box']),axis=1).ravel()
        for r in rows:
            x=np.array(r['start']);v=np.array(r['v'])
            assert abs(np.linalg.norm(v)-1)<1e-12
            assert [v['eps'] for v in r['variants']]==EPS
            for w in r['variants']:
                y=x+w['eps']*width*v
                assert bool(np.array_equal(x,y))==w['same_bits']
                assert float(np.linalg.norm((y-x)/width))==w['actual_eps']
            coord=r['ulp']['coord'];y=x.copy();y[coord]=np.nextafter(y[coord],np.inf)
            assert float(np.linalg.norm((y-x)/width))==r['ulp']['actual_eps']
            before,after=r['base']['label'],r['ulp']['r']['label']
            ulp_changes+=before!=after
            if before!=after and before.startswith('R') and after.startswith('R'):
                ulp_root_changes+=1
                av=inp['roots'][int(before[1:])]['answer'];bv=inp['roots'][int(after[1:])]['answer']
                ulp_target_changes+=abs(av-bv)>1e-6*max(1,abs(av),abs(bv))
            if r['base']['label']!=r['ulp']['r']['label'] and len([e for e in examples if e['id']==cid])<2:
                examples.append({'id':cid,'i':r['i'],'coord':coord,'x_hex':[float(z).hex() for z in x],
                  'x_ulp_hex':[float(z).hex() for z in y], 'before':r['base'],'after':r['ulp']['r']})
            recs=[r['base'],r['ulp']['r']]+[v['r'] for v in r['variants']]
            if 'repeat' in r:
                repeats+=1;assert r['base']['label']==r['repeat']['label'];recs.append(r['repeat'])
            for rec in recs:
                assert rec.get('nfev',0)<=80
                classes[rec['label']]+=1;local_calls+=1;local_seconds+=rec['sec']
        for j,e in enumerate(EPS):
            expected=sum(r['base']['label']!=r['variants'][j]['r']['label'] for r in rows)
            assert expected==int(curve[cid,e]['changes'])
        verify=json.loads((OUT/f'verify/{cid}.json').read_text())['rows']
        assert len(verify)==32
        for r in verify:
            for rec in [r['base']]+[v['r'] for v in r['variants']]:
                assert rec.get('nfev',0)<=320
                local_calls+=1;local_seconds+=rec['sec'];classes[rec['label']]+=1
        located=json.loads((OUT/f'patches/{cid}.json').read_text())
        assert len(located['attempts'])==2
        patches=located['patches']
        assert len(patches)==2
        for p in patches:
            assert len(p['trace'])==13
            recs=[p['trace'][0]['ra'],p['trace'][0]['rb']]+[t['r'] for t in p['trace'][1:]]
            for rec in recs:local_calls+=1;local_seconds+=rec['sec'];classes[rec['label']]+=1
        checks.append({'id':cid,'n_starts':len(rows),'epsilons':len(EPS),'cap320_points':len(verify),'patches':2})
        for r in inp['roots']:
            x=r['center'];err=None
            if cid=='AIME-2023-I-05':
                s,p,q=x;err=[p*p+q*q-s*s/2,s**4-s*s*(p+q)**2-56**2,s**4-s*s*(p-q)**2-90**2]
            elif cid=='AIME-2025-I-02':
                a,b=x;err=[a*a+b*b-91**2,48*b/7-288]
            elif cid=='HMMT-2014-FEB-GEO-06':
                a,b=x;err=[(a-5)**2+(b-6)**2-25,a*a+b*b-16]
            elif cid=='HMMT-2009-FEB-GEO-07':
                c,e,h=x;err=[e*e-25,(c-e)**2-81,c*h-168]
            elif cid=='HMMT-2011-FEB-ALGGEO-10':
                e,f=x;err=[e*f-338,e*f-6*e-13*f]
            if err is not None:
                assert max(abs(v) for v in err)<1e-6,(cid,err)
                poly.append({'id':cid,'root':x,'polynomial_residuals':err})
    assert repeats==192
    assert classes['T']==0 and classes['E']==0
    densecalls=0;denseseconds=0
    for cid in ['AIME-2023-I-05','AIME-2025-I-02']:
        rows=[]
        for p in sorted((OUT/'dense').glob(cid+'-*.json')):
            d=json.loads(p.read_text());rows+=d['rows']
            for r in d['rows']+d['verified']:
                recs=[r['base']]+[v['r'] for v in r['variants']]
                if 'ulp' in r:recs.append(r['ulp']['r'])
                if 'repeat' in r:recs.append(r['repeat'])
                for rec in recs:densecalls+=1;denseseconds+=rec['sec']
        assert sorted(r['i'] for r in rows)==list(range(1024))
    full=[]
    for folder,n in [('full',120),('full-mp',48),('full-recheck',len(json.loads((OUT/'recheck-jobs.json').read_text())))]:
        paths=dataio.paths(OUT/folder);assert len(paths)==n,(folder,len(paths),n)
        for p in paths:
            d=dataio.read(p);assert d['status']=='completed',p
            assert d['termination_reason']=='answer_found',p
            assert d['elapsed_seconds']<30
            assert d['q34_started_utc']>json.loads((OUT/'prediction.lock.json').read_text())['utc']
            if d['mode'] not in ('native','native-repeat'):assert d['intervention_calls']>0,p
            records=[]
            for f in dataio.paths(p.parent/'candidates',p.stem+'-[0-9][0-9].json'):records+=dataio.read(f)
            assert len(records)==d['candidate_record_count']
            full.append(d)
    controls=json.loads((OUT/'controls.json').read_text());assert controls['pass']
    compressed=json.loads((OUT/'compression.json').read_text())
    for rec in compressed['files']:
        raw=gzip.decompress((OUT/rec['path']).read_bytes())
        assert len(raw)==rec['uncompressed_bytes']
        assert hashlib.sha256(raw).hexdigest()==rec['uncompressed_sha256']
    save('ulp-examples.json',examples);save('polynomial-check.json',poly)
    files=[]
    for p in sorted(OUT.rglob('*')):
        if not p.is_file():continue
        size=p.stat().st_size;assert size<5_000_000,(p,size)
        if (p.name in ('manifest.json','verification.json') or p.suffix=='.so'
                or any(part in p.parts for part in ('plot-cache','__pycache__','logs'))):continue
        files.append({'path':str(p.relative_to(OUT)),'bytes':size,'sha256':sha(p)})
    save('manifest.json',{'utc':utc(),'files':files})
    save('verification.json',{'utc':utc(),'passed':True,'source_and_12_DSL_match_frozen_commit':True,
       'prediction_sha256_unchanged':True,'problems':checks,'same_input_replays':repeats,
       'primary_local_calls_including_patches_and_cap320':local_calls,'primary_local_seconds':local_seconds,
       'primary_all_labels':dict(classes),'supplement_local_calls':densecalls,
       'ulp_outcome_changes':ulp_changes,'ulp_known_root_changes':ulp_root_changes,
       'ulp_target_changes_between_known_roots':ulp_target_changes,
       'gzip_roundtrip_verified_files':len(compressed['files']),
       'supplement_local_seconds':denseseconds,'full_runs':len(full),
       'full_seconds':sum(r['elapsed_seconds'] for r in full),
       'max_full_seconds':max(r['elapsed_seconds'] for r in full),'full_time_limits':0,
       'files_audited':len(files),'total_bytes':sum(r['bytes'] for r in files),
       'largest_file':max(files,key=lambda r:r['bytes']),
       'concurrency_limit':3,'blas_threads':1,'batch_time_limit_seconds':170})
    print(json.dumps(json.loads((OUT/'verification.json').read_text()),indent=2))

if __name__=='__main__':audit()
