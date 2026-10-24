"""Audit complete slot coverage, source identity, paired starts and raw evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from collections import Counter
from stage2_common import *


def stream_hash(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(1<<20):h.update(b)
    return h.hexdigest()


def main():
    source=assert_identity();errors=[];checks=Counter();prepared={}
    for name in ('implementation.lock.json','full-implementation.lock.json','jacobian-implementation.lock.json'):
        lock=json.loads((OUT/'execution'/name).read_text())
        for script,expected_hash in lock['files'].items():
            if digest(OUT/script)!=expected_hash:errors.append(f'implementation hash {script}')
            checks['implementation_hashes']+=1
    import numpy as np
    ids=sorted(r['id'] for r in json.loads((OUT/'selection.json').read_text()))
    for i,cid in enumerate(ids):
        p=json.loads((RAW/'prepared'/f'{cid}.json').read_text())
        if 'starts' in p:
            bounds=np.array(p['bounds'])
            for k,x in enumerate(p['starts']):
                expected=np.random.default_rng([410241,i,k]).uniform(bounds[:,0],bounds[:,1]).tolist()
                if x!=expected:errors.append(f'start RNG mismatch {cid}:{k}')
            checks['common_start_sets']+=1
        prepared[cid]=p
    local_jobs=json.loads((RAW/'local-jobs.json').read_text())
    allkeys=set();successful={}
    for i,expected in enumerate(local_jobs):
        d=RAW/'local'/f'{i:04d}'
        rows=[json.loads(l) for l in (d/'records.jsonl').read_text().splitlines()]
        starts=[json.loads(l) for l in (d/'starts.jsonl').read_text().splitlines()]
        key=lambda r:(r['id'],r['arm'],r['k'])
        if [key(r) for r in rows]!=[key(r) for r in expected]:errors.append(f'local slot order {i}')
        if len({key(r) for r in starts})!=len(starts):errors.append(f'repeated start {i}')
        for r in rows:
            if key(r) in allkeys:errors.append(f'duplicate local {key(r)}')
            allkeys.add(key(r));cid=r['id']
            if cid not in prepared:prepared[cid]=json.loads((RAW/'prepared'/f'{cid}.json').read_text())
            if r.get('start') is not None and r['start']!=prepared[cid]['starts'][r['k']]:errors.append(f'paired start changed {key(r)}')
            if r.get('seed')!=410241:errors.append(f'wrong local seed {key(r)}')
            if r['success']:
                successful.setdefault((cid,r['arm']),[]).append(r['k'])
                v=r['verification']
                if not (v['success'] and v['float']['norm']<=1e-8 and float(v['hp']['norm'])<=1e-8 and v['float']['guard_ok'] and v['float']['hard_ok'] and v['hp']['guard_ok'] and v['hp']['hard_ok']):errors.append(f'acceptance mismatch {key(r)}')
            checks['local_slots']+=1
    jobs=json.loads((RAW/'full-jobs.json').read_text())
    for i,r in enumerate(jobs):
        d=RAW/'full'/f'{i:04d}';v=json.loads((d/'verification.json').read_text())
        if any(v[k]!=r[k] for k in ('id','arm','seed')):errors.append(f'full identity {i}')
        if v['T']<.001 or v['T']>180:errors.append(f'full T range {i}')
        if (d/'solver-result.json').exists():
            result=json.loads((d/'solver-result.json').read_text())
            if result['engine']['source_hash']!=source:errors.append(f'full source {i}')
            resources=result['requested_resources']
            if resources!={'time_limit_seconds':180.0,'cores':1,'seed':r['seed']}:errors.append(f'full resource budget {i}')
            info=(result.get('diagnostics') or {}).get('process_info',{})
            if info.get('import_root') and info['import_root']!=str(CLEAN/'src/geosolver'):errors.append(f'full import root {i}')
        if (d/'candidates.jsonl').exists():
            count=0;candidate_times={}
            for line in (d/'candidates.jsonl').open():
                c=json.loads(line)
                if c['index']!=count:errors.append(f'candidate order {i}:{count}')
                candidate_times[count]=c['t'];count+=1
            if v.get('observation_complete') and count!=v['candidate_count']:errors.append(f'candidate count {i}')
            checkfile=d/'candidate-checks.jsonl';passed=[];seen=set()
            if checkfile.exists():
                for line in checkfile.open():
                    c=json.loads(line)
                    if c['index'] in seen:errors.append(f'duplicate verification {i}:{c["index"]}')
                    seen.add(c['index'])
                    if c['t']!=candidate_times[c['index']]:errors.append(f'changed birth time {i}:{c["index"]}')
                    if c['success'] and 0<=c['t']<180:passed.append(c['t'])
            if not v['censored'] and v['T']!=max(.001,min(passed)):errors.append(f'not earliest candidate {i}')
        checks['full_slots']+=1
    jjobs=json.loads((RAW/'jacobian-jobs.json').read_text())
    expected_j={(cid,arm,k) for (cid,arm),ks in successful.items() for k in sorted(ks)[:5]}
    actual_j=[(r['id'],r['arm'],r['k']) for r in jjobs]
    if set(actual_j)!=expected_j or len(actual_j)!=len(expected_j):errors.append('J endpoint selection')
    for i,r in enumerate(jjobs):
        d=RAW/'jacobian'/f'{i:04d}'
        rec=json.loads((d/'done.json').read_text())
        if any(rec[k]!=r[k] for k in ('id','arm','k')):errors.append(f'J identity {i}')
        if rec['status']=='measured':
            m,n=rec['m'],rec['n']
            if set(rec['steps'])!={'1e-5','1e-6','1e-7'}:errors.append(f'J difference steps {i}')
            if rec['padded_zero_count']!=max(0,n-m):errors.append(f'J padding {i}')
            if len(rec['refined_x'])!=n or float(rec['refined_norm'])>1e-24:errors.append(f'J refined endpoint {i}')
            for h,step in rec['steps'].items():
                for version in ('raw','normalized'):
                    spectrum=step[version]
                    values=[float(x) for x in spectrum['singular_values']]
                    if len(values)!=n or not all(math.isfinite(x) and x>=0 for x in values):errors.append(f'J spectrum {i}:{h}:{version}')
                    if float(spectrum['sigma_min'])!=min(values) or float(spectrum['sigma_max'])!=max(values):errors.append(f'J extrema {i}:{h}:{version}')
                    if n>m and values[-(n-m):]!=[0.]*(n-m):errors.append(f'J missing structural zeros {i}:{h}:{version}')
            checks['jacobian_measured']+=1
        checks['jacobian_selected']+=1
    large=[]
    for p in OUT.rglob('*'):
        if p.is_file() and p.stat().st_size>5_000_000:large.append(str(p.relative_to(OUT)))
    if large:errors.append(f'repository files exceed 5MB: {large}')
    save(OUT/'execution/final-audit.json',dict(utc=utc(),checks=dict(checks),errors=errors,passed=not errors,source_hash=source))
    assert not errors,errors
    manifest={}
    for p in sorted(RAW.rglob('*')):
        if p.is_file():manifest[str(p.relative_to(RAW))]={'bytes':p.stat().st_size,'sha256':stream_hash(p)}
    save(OUT/'raw-manifest.json',dict(root=str(RAW),utc=utc(),files=manifest,
             files_count=len(manifest),total_bytes=sum(r['bytes'] for r in manifest.values())))
    assert (OUT/'raw-manifest.json').stat().st_size<=5_000_000
    print(json.dumps({'passed':True,'checks':dict(checks),'raw_files':len(manifest),'raw_bytes':sum(r['bytes'] for r in manifest.values())}))


if __name__=='__main__':main()
