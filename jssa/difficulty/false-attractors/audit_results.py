"""Independent bookkeeping and coordinate checks; no local search."""
from __future__ import annotations
from pathlib import Path
import csv,gzip,hashlib,json,math,os,sys,time
from collections import Counter,defaultdict
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.dont_write_bytecode=True
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'jssa/difficulty'))
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
from classify_endpoints import Diagnostics, clean, label, finite_x, protect, dump
from probe_basins import construction_coordinates, answer_float

def main():
    protect();t0=time.monotonic()
    summary=json.loads((HERE/'summary.json').read_text())
    manifest=json.loads((HERE/'input-manifest.json').read_text())
    assert len(list((HERE/'classified').glob('*.json')))==292
    assert hashlib.sha256((HERE/'preregistration.md').read_bytes()).hexdigest()==manifest['preregistration_sha256']
    source_records=Counter();branch_errors=Counter();raw_votes=Counter();raw_classes=Counter();unmeasured=[]
    cases={};recheck=[];d_candidates=[];hit_flags=[];primary_flags=Counter();masks0=[]
    source_files_changed=[]
    for entry in manifest['files']:
        p=ROOT/entry['path']
        data=p.read_bytes()[:entry['bytes_used']]
        same=hashlib.sha256(data).hexdigest()==entry['sha256']
        if not same:source_files_changed.append(entry['path'])
    seen=set()
    for f in sorted((HERE/'inputs').glob('*.gz')):
        assert hashlib.sha256(f.read_bytes()).hexdigest()==manifest['snapshots'][f.name]
        o=json.loads(gzip.decompress(f.read_bytes()));cases[o['id']]=o
        source_records.update(r['source']+'/'+r['arm'] for r in o['records'])
    assert dict(source_records)==manifest['records']
    for f in sorted((HERE/'classified').glob('*.json')):
        o=json.loads(f.read_text());assert o['status']=='ok',o
        if o['hit_control'].get('ab',0):hit_flags.append({'id':o['id'],**o['hit_control']})
        if o['meta']['mask_reference']=='starts_only':masks0.append(o['id'])
    for f in sorted((HERE/'classified').glob('*.jsonl.gz')):
        for row in map(json.loads,gzip.decompress(f.read_bytes()).splitlines()):
            if row.get('branch_error'):branch_errors[row['branch_error']]+=1
            if row['source']!='raw0':continue
            key=(row['id'],row['source'],row['arm'],row['k']);assert key not in seen;seen.add(key)
            raw_votes[row['vote']]+=1;raw_classes[row['cls']]+=1
            assert row['ab']==(row['a'] or row['b'])
            assert sum(row['vote']==v for v in ('a','b','c','d','e','unknown'))==1
            for flag in 'abcde':primary_flags[flag]+=row[flag]
            if row['vote']=='unknown':unmeasured.append({'id':row['id'],'k':row['k'],'cls':row['cls'],
                'n_points_defined':row.get('n_points_defined'),'n_circles_defined':row.get('n_circles_defined'),
                'finite_residual':row.get('residual') is not None,'error':row.get('evaluation_error')})
            if row.get('d'):
                pack=cases[row['id']]
                r=next(r for r in pack['records'] if r['source']=='raw0' and r['k']==row['k'])
                width=np.diff(np.array(pack['box']),axis=1).ravel()
                hits=[rr['x'] for rr in pack['records'] if rr['source']=='raw0' and rr['cls']=='hit' and 'x' in rr]
                distance=min((float(np.linalg.norm((np.array(r['x'])-h)/width)) for h in hits),default=math.nan)
                d_candidates.append({'id':row['id'],'k':row['k'],'value':row.get('answer_recomputed'),
                    'hp_residual':row.get('hp_residual'),'nearest_hit_box_normalized_distance':distance})
    assert not branch_errors,branch_errors
    assert sum(raw_votes.values())==summary['primary']['failed_records']
    for flag in 'abcde':assert primary_flags[flag]==summary['primary'][flag]
    assert not summary['basins_discrepancies']
    selected=['AIME-2006-I-01','AIME-2010-II-14','HMMT-2007-FEB-GEO-04',
              'HMMT-2024-FEB-GEO-02','JMO-2017-PRE-01','HMMT-2025-FEB-GEO-04',
              'HMMT-2008-FEB-GEO-10','aime-2002-2-15']
    coordinate_results=[];boundary_results=[]
    for cid in selected:
        pack=cases[cid];diag=Diagnostics(pack)
        picks=[]
        for hit in (True,False):
            options=[r for r in pack['records'] if r['source']=='raw0' and (r['cls']=='hit')==hit and finite_x(r.get('x'),diag.n)]
            if options:picks.append(options[0])
        coords={};coord_errors={}
        for name in diag.names:
            try:coords[name]=construction_coordinates(pack['case']['dsl'],[name])
            except Exception as exc:coord_errors[name]=repr(exc)
        for r in picks:
            points=diag.fig.at(r['x'])[0];values=dict(zip(diag.bundle.var_names,r['x']))
            for name in diag.names:
                if name not in coords or name not in points:continue
                reference=[]
                for axis in ('x','y'):
                    var_names,ev=coords[name][axis+'_'+name]
                    reference.append(answer_float(ev,[values[n] for n in var_names]))
                good=all(v is not None and math.isfinite(v) for v in reference)
                err=float(np.linalg.norm(points[name]-reference)/max(diag.S0,np.linalg.norm(reference),1e-300)) if good else None
                coordinate_results.append({'id':cid,'k':r['k'],'cls':r['cls'],'point':name,'relative_error':err,
                                           'reference_defined':good})
        # Check stored G b6 against the deterministic coordinate axes at saved failed points.
        available=[r for r in pack['records'] if r['source']=='raw0' and r['cls']!='hit' and str(r['k']) in pack['G_diagnostics']][:8]
        for r in available:
            old=pack['G_diagnostics'][str(r['k'])]
            if 'b6' not in old or diag.hard(r['x']) is not True:continue
            observed,_=diag.boundary(r['x'],r['k'],None)
            boundary_results.append({'id':cid,'k':r['k'],'saved_b6':bool(old['b6']),'reevaluated':observed,
                                     'same':observed==bool(old['b6'])})
    defined=[r['relative_error'] for r in coordinate_results if r['reference_defined']]
    assert max(defined)<1e-8,max(defined)
    questionable_ids={r['id'] for r in hit_flags}|set(masks0)
    pp=list(csv.DictReader((HERE/'per-problem.csv').open()))
    clean_pp=[r for r in pp if r['id'] not in questionable_ids]
    stress={'exploratory':True,'excluded_problems':len(questionable_ids),'retained_problems':len(clean_pp),
       'ab':sum(int(r['ab']) for r in clean_pp),'finite_failed':sum(int(r['finite_failed']) for r in clean_pp),
       'main_ab_retained':sum(r['main_cause'] in ('a','b') for r in clean_pp),
       'note':'Exclude all no-hit problems and all problems with any hit flagged a/b; keep main criteria unchanged.'}
    unknown_by_problem=Counter(r['id'] for r in unmeasured)
    audit={'preregistration_unchanged':True,'snapshots_hash_match':True,'sources_prefix_changed':source_files_changed,
       'source_record_counts_match':True,'primary_failed_unique':len(seen),'primary_votes':dict(raw_votes),
       'branch_errors':dict(branch_errors),'coordinate_reference_points':len(coordinate_results),
       'coordinate_reference_defined':len(defined),'coordinate_max_relative_error':max(defined),
       'boundary_rechecks':len(boundary_results),'boundary_disagree':sum(not r['same'] for r in boundary_results),
       'hit_flags':hit_flags,'unknown_by_problem':dict(unknown_by_problem),
       'numerical_branch_candidates':d_candidates,'branch_existence_proved':0,
       'stress_exclude_unreliable_reference':stress,'seconds':time.monotonic()-t0,
       'no_optimization':True}
    dump(HERE/'audit.json',audit);dump(HERE/'coordinate-checks.json',coordinate_results)
    dump(HERE/'boundary-checks.json',boundary_results)
    print(json.dumps(clean({k:v for k,v in audit.items() if k not in ('numerical_branch_candidates','unknown_by_problem')}),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
