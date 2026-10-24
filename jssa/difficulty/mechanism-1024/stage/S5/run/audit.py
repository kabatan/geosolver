"""Read-only execution, pairing, source, digits, predictions and file-size audit."""
import ast
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from mpmath import mp
mp.dps=750
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text());ROOT=Path(M['scratch']);checks=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text()) if p.exists() else None
for coll in ['files','source_files']:
    for path,expected in M[coll].items():assert sha(Path(path))==expected,path
assert (ROOT/'manifest.json').read_bytes()==(OUT/'pre-run-hashes.json').read_bytes()
checks.append('fixed classifications, targets, stage (1) inputs, scripts, rules, sources and manifest unchanged')
# The numeric S3 branches and S1 search/scales branches must be copied verbatim.
s3=(OUT.parent.parent/'S3/run/worker.py').read_text();s1=(OUT.parent.parent/'S1/worker.py').read_text();worker=(OUT/'worker.py').read_text()
for mode in ['refine','measure','references','verify']:
    def branch(src,name):
        tree=ast.parse(src);node=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and ast.get_source_segment(src,n.test) in [f'MODE == "{name}"', 'MODE in ("measure", "iterations")' if name=='measure' else ''])
        return [ast.dump(n,include_attributes=False) for n in node.body]
    assert branch(s3,mode)==branch(worker,mode),mode
assert branch(s1,'scales')==branch(worker,'scales')
checks.append('S3 refine/measure/references/verify numeric branches and S1 scales branch AST identical; search capture adds metadata only')
events=[json.loads(l) for l in (ROOT/'events.jsonl').read_text().splitlines()];active=set();peak=0;started=Counter();ended=Counter()
for e in events:
    s=e['stage']
    if s.endswith('_start') and 'case_id' in e:
        key=e['case_id'],s[:-6],e.get('arm');assert key not in active;active.add(key);peak=max(peak,len(active));started[key]+=1
    elif s.endswith('_end') and 'case_id' in e:
        key=e['case_id'],s[:-4],e.get('arm');assert key in active;active.remove(key);ended[key]+=1
assert not active and peak<=8 and started==ended and all(v==1 for v in started.values())
assert sum(e['stage']=='problem_done' for e in events)==32
assert sum(k[1]=='search' for k in started)==32
assert {k[0] for k in started}=={t['case_id'] for t in M['inputs']}
checks.append('32 fixed problems; one seed-0 search each; every stage at most once; peak concurrency <=8')
with (OUT/'per-problem.csv').open() as f:table={r['case_id']:r for r in csv.DictReader(f)}
J=read(OUT/'judgments.json');paired=0;digits_by_case={};failure=[]
for task in M['inputs']:
    case=task['case_id'];d=ROOT/'runs'/case;p=table[case];assert p['type']==task['type'] and p['prediction']==task['prediction']
    assert sha(d/'input.json')==task['sha256']
    init=read(d/'initial.json');snap=read(d/'initial-snapshot.json');uids=init['candidate_uids'] if init else [];paired+=len(uids)
    if init:
        assert sha(d/'initial.pkl')==snap['initial_sha256'];assert sha(d/'initial.json')==snap['initial_json_sha256'];assert init['seed']==0
    vals={}
    for mode in ['search','scales','references','refine','measure','verify']:
        for arm in ['T0','T1','T2'] if mode in ['refine','measure','verify'] else [None]:
            receipt=read(d/(mode+('.'+arm if arm else '')+'.execution.json'))
            if receipt:
                assert len(receipt['affinity'])==1 and receipt['affinity'][0] in M['cpus']
                assert all(v=='1' for v in receipt['threads'].values());assert receipt['seed']==0
                assert receipt['switches']==({'GEOSOLVER_S3_TANGENCY_MODE':arm} if mode=='refine' else {})
                assert receipt['source_hash']==M['frozen_source_hash' if mode in ['references','verify'] else 'source_hash']
    for arm in ['T0','T1','T2']:
        r=read(d/(arm+'.refinement.json'));me=read(d/(arm+'.measure.json'));v=read(d/(arm+'.verification.json'))
        if r:
            assert r['initial_sha256']==snap['initial_sha256'];assert r['scales_sha256']==sha(d/'scales.json')
            assert set(r['candidate_seconds'])<=set(uids);assert r['source_hash']==M['source_hash']
        if v:assert v['source_hash']==M['frozen_source_hash']
        usable=[x for x in (me or {}).get('rows',[]) if x.get('absolute_error') is not None and mp.isfinite(mp.mpf(x['absolute_error']))]
        if usable:
            b=min(usable,key=lambda x:mp.mpf(x['absolute_error']));err=mp.mpf(b['absolute_error']);dig=min(mp.mpf(600),-mp.log10(err)) if err else mp.mpf(600)
            assert b['candidate_uid']==p[arm+'_best_candidate_uid'];assert abs(dig-mp.mpf(p[arm+'_best_error_digits']))<mp.mpf('1e-20');vals[arm]=dig
        else:assert not p[arm+'_best_error_digits'];vals[arm]=None
    digits_by_case[case]=vals
    for key,sigma in task['sigma'].items():
        assert p[key]==sigma
        if sigma:assert 'e' in sigma.lower(),(case,key)
checks.append('single CPU affinity, internal threads=1, switches, source hashes, same initial pickle/config/order/scales and frozen verifier checked')
checks.append('best candidate and digits independently recomputed from saved 700-digit errors; all sigma retain explicit exponents')
for u,typ in [('U1','P'),('U2','N'),('U3','B')]:
    group=[t for t in M['inputs'] if t['type']==typ];hits=[]
    for t in group:
        v=digits_by_case[t['case_id']];a,b=v['T1'],v['T2']
        hit=None if b is None or (typ!='B' and a is None) else bool(b-a>=40) if typ=='P' else bool(abs(b-a)<=20) if typ=='N' else bool(b<300)
        hits.append(hit)
    n=len(hits);h=hits.count(True);mi=hits.count(None);needed=(4*n+4)//5
    verdict='判定不能' if n<2 else '当たり' if h>=needed else '外れ' if h+mi<needed else '判定不能'
    assert J['predictions'][u]['judgment']==verdict
    assert J['predictions'][u]['success']==h and J['predictions'][u]['missing']==mi
checks.append('U1/U2/U3 recomputed with fixed type denominators, missing separate and n<2 indeterminate')
for root in [OUT,ROOT]:
    for p in root.rglob('*'):
        if p.is_file():assert p.stat().st_size<3_000_000,p
checks.append('all generated files <3,000,000 bytes')
bad=[e for e in events if e.get('returncode',0)!=0]
receipt=dict(status='ok' if not bad and not J['missing_stages'] else 'completed_with_missing_stages',checks=checks,nonzero_stages=bad,
    paired_initial_candidates=paired,peak_concurrent_stages=peak,search_count=32,refine_count=sum(k[1]=='refine' for k in started),
    fixed_classification_counts=J['fixed_classification_counts'],audit_script_sha256=sha(Path(__file__)))
(OUT/'audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
(OUT/'raw-hashes.json').write_text(json.dumps({str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(ROOT.rglob('*')) if p.is_file()},indent=2)+'\n')
(OUT/'output-hashes.json').write_text(json.dumps({p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in ['output-hashes.json','progress.md']},indent=2)+'\n')
with (OUT/'progress.md').open('a') as f:f.write('\n全32問を終了。監査: '+receipt['status']+'。\n')
print(json.dumps(receipt,ensure_ascii=False))
