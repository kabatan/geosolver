"""Exploratory census of saved LM endpoints; no optimization is run.

Only seed 0 spatial labels are examined here. Seed 1 remains unopened for
the spatial comparisons (its aggregate counts and schema were inspected).
"""
from pathlib import Path
import json, time, hashlib, csv
from collections import Counter
import numpy as np
from scipy.spatial.distance import cdist, pdist, squareform
from scipy.sparse.csgraph import connected_components

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
RAW = ROOT / 'jssa/difficulty/minima/raw-323'

def read(cid, seed=0):
    folder = 'raw-323' if seed == 0 else 'raw-323-seed1'
    return json.loads((ROOT / 'jssa/difficulty/minima' / folder / (cid+'.json')).read_text())

def starts(d):
    rs = d['records']; n = d['n_vars']; box = np.asarray(d['box'], float)
    assert all(r['k'] == k for k, r in enumerate(rs))
    assert not d.get('dsl_override') and not d.get('init_from')
    assert not d.get('feasible_starts') and not d.get('zero_prefix')
    u = np.random.default_rng(d['seed']).random((len(rs), n))
    x = box[:, 0] + u*(box[:, 1]-box[:, 0])
    if all('start' in r for r in rs):
        assert np.array_equal(x, np.asarray([r['start'] for r in rs]))
    return u

def cluster(x, tol):
    if not len(x): return np.array([], int), np.array([], int)
    _, lab = connected_components(squareform(pdist(x)) <= tol, directed=False)
    return lab, np.bincount(lab)

def quartile(y, z):
    lo, hi = np.quantile(z, [.25, .75])
    a = z <= lo; b = z >= hi
    return dict(q25=float(lo), q75=float(hi), near_n=int(a.sum()), far_n=int(b.sum()),
                near_hits=int(y[a].sum()), far_hits=int(y[b].sum()),
                near_p=float(y[a].mean()), far_p=float(y[b].mean()),
                far_minus_near=float(y[b].mean()-y[a].mean()))

def write_csv(name, rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def pick(rows, keys):
    return [{k:r.get(k) for k in keys} for r in rows]

def run():
    t0=time.monotonic(); rows=[]; shell=[]; clusters=[]; rank=[]; count=Counter(); manifest={}
    for f in sorted(RAW.glob('*.json')):
        d=json.loads(f.read_text()); manifest[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
        rs=d.get('records', []); count[d['status']]+=1
        if not rs: continue
        u=starts(d); count['reconstructed_starts_equal_saved']+=len(rs)
        y=np.array([r['cls']=='hit' for r in rs], bool); n=len(rs); nv=d['n_vars']; cid=f.stem
        box=np.array(d['box']); width=box[:,1]-box[:,0]
        x=(np.array([r['x'] for r in rs])-box[:,0])/width
        xx=x[y & np.isfinite(x).all(axis=1)]
        row=dict(id=cid,n=n,n_vars=nv,hits=int(y.sum()),p=float(y.mean()),n_refs=len(d['references']))
        for tol in [1e-4,1e-3,1e-2]:
            lab, sz=cluster(xx,tol)
            suffix=str(tol)
            row['hit_clusters_'+suffix]=len(sz)
            row['largest_hit_share_'+suffix]=float(max(sz)/sum(sz)) if len(sz) else None
            if tol==1e-3 and len(sz):
                p=sz/sz.sum(); row['hit_effective_clusters']=float(1/(p@p))
                row['hit_singletons']=int((sz==1).sum())
                for j,s in enumerate(sorted(sz,reverse=True)):
                    clusters.append(dict(id=cid,rank=j+1,count=int(s),conditional_share=float(s/sz.sum()),total_share=float(s/n)))
                centers=np.array([xx[lab==j].mean(0) for j in range(len(sz))])
                if len(sz)>=2 and min(sz)>=5 and len(sz)<=8:
                    start_hit=u[y & np.isfinite(x).all(axis=1)]
                    nearest=cdist(start_hit,centers).argmin(1)
                    row['nearest_destination_agreement']=float((nearest==lab).mean())
                    row['branch_sizes']=json.dumps(sz.tolist())
        if len(xx):
            dd=cdist(u,xx).min(axis=1)
            s=quartile(y,dd); shell.append(dict(id=cid,metric='distance_to_saved_hit',**s))
            row['root_far_minus_near']=s['far_minus_near']
        for metric,z in [('distance_to_box_center',np.linalg.norm(u-.5,axis=1)),('distance_to_box_boundary',np.min(np.minimum(u,1-u),axis=1))]:
            s=quartile(y,z);shell.append(dict(id=cid,metric=metric,**s))
            row[metric+'_far_minus_near']=s['far_minus_near']
        dist=squareform(pdist(u));np.fill_diagonal(dist,np.inf)
        nearest=dist.argmin(1); equal=y==y[nearest]
        row['one_nn_agreement']=float(equal.mean())
        row['independent_agreement']=float(y.mean()**2+(1-y.mean())**2)
        row['nn_distance_median']=float(np.median(dist[np.arange(n),nearest]))
        row['nn_excess_agreement']=row['one_nn_agreement']-row['independent_agreement']
        # Rank diagnostics are local, saved at the first hit per target value.
        for ref,h in d.get('first_hit',{}).items():
            sv=np.array(h['svals']); rk=int((sv>max(sv,default=0)*1e-8).sum())
            rank.append(dict(id=cid,ref=ref,n_vars=nv,rank=rk,nullity=nv-rk))
        rows.append(row)
    write_csv('exploratory-problems.csv',rows);write_csv('exploratory-spatial-contrasts.csv',shell)
    write_csv('hit-cluster-sizes.csv',clusters);write_csv('saved-hit-ranks.csv',rank)
    eligible=[r for r in rows if r['n']>=100 and 20<=r['hits']<=r['n']-20]
    select=sorted([r for r in eligible if r['root_far_minus_near']>=.2],key=lambda r:-r['root_far_minus_near'])
    summary=dict(counts=dict(count),n_questions=len(rows),eligible_spatial=len(eligible),
                 near_inversion_candidates=pick(select,['id','n_vars','n','hits','root_far_minus_near']),
                 inverse_direction_large=sum(r['root_far_minus_near']<=-.2 for r in eligible),
                 top_non_voronoi=pick(sorted([r for r in rows if 'nearest_destination_agreement' in r],key=lambda r:r['nearest_destination_agreement'])[:12],['id','hits','branch_sizes','nearest_destination_agreement']),
                 top_cluster_counts=pick(sorted(rows,key=lambda r:-r['hit_clusters_0.001'])[:12],['id','n_vars','hits','hit_clusters_0.001','hit_singletons']),
                 top_center_advantage=pick(sorted(eligible,key=lambda r:-r['distance_to_box_center_far_minus_near'])[:12],['id','n_vars','p','distance_to_box_center_far_minus_near']),
                 seconds=time.monotonic()-t0)
    (OUT/'exploratory-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    (OUT/'seed0-input-hashes.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':run()
