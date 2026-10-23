"""Check saved evidence and a post-result static dispatch example; no optimizer."""
import ast
import copy
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def dump(name, data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def source_hash():
    h=hashlib.sha256()
    for p in sorted((ROOT/'src').rglob('*.py')):
        h.update(str(p.relative_to(ROOT)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def main():
    lock=json.loads((OUT/'registration-lock.json').read_text())
    locked={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest()==v for n,v in lock['files'].items()}
    assert all(locked.values())
    sh=source_hash()
    assert sh==lock['src_sha256']
    pairs=json.loads((OUT/'stimuli.json').read_text())
    all_rows=[]; checks=[]; direct_matches=long_matches=0
    for pair in pairs:
        rows=json.loads((OUT/'raw'/f"{pair['id']}.json").read_text())['rows']
        index={(r['mode'],r['seed'],r['k']):r for r in rows}
        assert len(index)==len(rows)
        main_names=list(pair['variants'])
        expected=main_names+(['direct_near','direct_far','long_near','long_far'] if pair['group']=='S' else [])
        assert len(rows)==64*len(expected)
        for seed in [220231,220232]:
            for k in range(32):
                group=[index[(name,seed,k)] for name in expected]
                assert all(r['start']==group[0]['start'] for r in group)
                for name in ['near','far'] if pair['group']=='S' else []:
                    direct_matches+=index[('power_'+name,seed,k)]['hit']==index[('direct_'+name,seed,k)]['hit']
                    long_matches+=index[('power_'+name,seed,k)]['hit']==index[('long_'+name,seed,k)]['hit']
        if pair['group']=='S':
            a,b=copy.deepcopy(pair['variants']['power_near']['dsl']),copy.deepcopy(pair['variants']['power_far']['dsl'])
            a.pop('id'); b.pop('id')
            assert a['conditions'][-1]['right']!=b['conditions'][-1]['right']
            a['conditions'][-1]['right']=b['conditions'][-1]['right']
            assert a==b
        else:
            a,b=copy.deepcopy(pair['variants']['easy']['dsl']),copy.deepcopy(pair['variants']['hard']['dsl'])
            assert a.pop('target')!=b.pop('target')
            assert a==b
        for r in rows:
            assert 'error' not in r
            x,y=r['x']
            if pair['group']=='S':
                a,h=float(pair['a']),float(pair['h'])
                s=-1 if r['mode'].endswith('far') else 1
                if r['mode'].startswith('length'):
                    v=[math.hypot(x+a,y)-math.sqrt(a*a+1),
                       math.hypot(x-a,y)-math.sqrt(a*a+1),
                       math.hypot(x,y-h)-abs(s-h)]
                else:
                    v=[(x+a)**2+y*y-a*a-1,(x-a)**2+y*y-a*a-1,
                       x*x+(y-h)**2-(s-h)**2]
                err=math.hypot(x,y-s)
            else:
                L,u,vv=pair['shape']
                v=[x*x+y*y-u*u-vv*vv,(x-L)**2+y*y-(u-L)**2-vv*vv]
                err=min(math.hypot(x-u,y-vv),math.hypot(x-u,y+vv))
            norm=math.sqrt(sum(z*z for z in v))
            assert abs(norm-r['residual'])<=1e-8*max(1,norm)
            box=all(lo<=z<=hi for z,(lo,hi) in zip(r['x'],pair['bounds']))
            geom=box and norm<=1e-8 and r['guard'] and r['hard'] and err<=1e-5
            assert geom==r['geometry_hit']
            name=r['mode']
            if name.startswith('direct_') or name.startswith('long_'):
                name='power_'+name.split('_')[1]
            ref=float(pair['variants'][name]['reference'])
            answer_ok=r['answer'] is not None and abs(r['answer']-ref)<=1e-6*max(1,abs(ref))
            assert r['hit']==(geom and answer_ok)
        checks.append({'pair':pair['id'],'rows':len(rows),'single_semantic_change':True,'labels_rechecked':True})
        all_rows+=rows
    assert len(all_rows)==6400
    mode_counts={}
    for r in all_rows:
        key=(r['pair'],r['mode'])
        mode_counts.setdefault(key,[0,0])
        mode_counts[key][0]+=1
        mode_counts[key][1]+=int(r['hit'])
    for r in csv.DictReader((OUT/'per-mode.csv').open()):
        assert mode_counts[(r['pair'],r['mode'])]==[int(r['n']),int(r['hits'])]
    s_table=list(csv.DictReader((OUT/'S-all-pairs.csv').open()))
    h_table=list(csv.DictReader((OUT/'H-all-pairs.csv').open()))
    for r in s_table:
        for mode in ['power_near','power_far','length_near','length_far',
                     'direct_near','direct_far','long_near','long_far']:
            assert int(r[mode])==mode_counts[(r['pair'],mode)][1]
    for r in h_table:
        for mode in ['easy','hard']:
            assert int(r[mode+'_hits'])==mode_counts[(r['pair'],mode)][1]
    old_summary=json.loads((OUT/'summary.json').read_text())
    assert old_summary['total_rows']==len(all_rows)
    assert old_summary['S_main_pairs_pass']==sum(int(r['power_near'])-int(r['power_far'])>=13 for r in s_table)
    assert old_summary['S_encoding_misses']==[r['pair'] for r in s_table if int(r['power_near'])-int(r['length_near'])<13]
    for p in OUT.glob('*.py'):
        ast.parse(p.read_text(),filename=str(p))
    broken=[]
    for p in OUT.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' in target or target.startswith('#'):
                continue
            target=target.split('#')[0]
            if not (p.parent/target).exists():
                broken.append({'file':p.name,'target':target})
    assert not broken,broken
    largest=max((p.stat().st_size,str(p.relative_to(OUT))) for p in OUT.rglob('*') if p.is_file())
    assert largest[0]<10_000_000
    human=list(csv.DictReader((ROOT/'jssa/difficulty/ghost-1023/human_feat.csv').open()))
    human_valid=[r for r in human if r['human'] and math.isfinite(float(r['human']))]
    old=[]
    for p in sorted((ROOT/'jssa/difficulty/minima/raw-323').glob('*.json')):
        d=json.loads(p.read_text())
        old.append({k:d.get(k) for k in ['case_id','n_vars','n_constraints']})
    under=[r for r in old if r['n_vars']>r['n_constraints']]
    summary={'audited_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
             'frozen_hashes_match':locked,'source_hash_matches':True,'src_sha256':sh,
             'all_rows':len(all_rows),'rows_independently_reclassified':len(all_rows),
             'saved_aggregate_counts_match':True,
             'direct_hit_labels_match_out_of_1280':direct_matches,
             'long_hit_labels_match_out_of_1280':long_matches,
             'maximum_seconds_per_start':max(r['seconds'] for r in all_rows),
             'maximum_native_residual_evaluations':max(r['telemetry_evaluations'] for r in all_rows),
             'broken_local_links':broken,'largest_file':{'bytes':largest[0],'name':largest[1]},
             'total_bytes_at_audit':sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),
             'legacy_raw_files':len(old),'legacy_positive_variables':sum(r['n_vars']>0 for r in old),
             'legacy_underdetermined':under,
             'legacy_human':{c:sum(r['contest']==c for r in human_valid) for c in sorted(set(r['contest'] for r in human_valid))},
             'pair_checks':checks,'new_optimizer_calls':0}
    dump('verification.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['pair_checks','legacy_underdetermined']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
