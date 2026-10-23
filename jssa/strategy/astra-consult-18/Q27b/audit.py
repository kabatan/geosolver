"""Read-only source census and checks of the rejected observations."""
from explore import OUT, ROOT, read, starts, cluster, write_csv
from collections import Counter, defaultdict
from pathlib import Path
import csv, json
import numpy as np

def table(path):return list(csv.DictReader((ROOT/path).open()))

def main():
    a=table('jssa/strategy/astra-consult-18/Q27b/exploratory-problems.csv')
    rank=table('jssa/strategy/astra-consult-18/Q27b/saved-hit-ranks.csv')
    full=table('jssa/results/stage-profile-20261023/per-case.csv')
    algebra=table('jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv')
    precision=table('jssa/strategy/astra-consult-18/q21b-number-theory/problem-summary.csv')
    feas0=table('jssa/difficulty/start-feasibility-1023/per-problem.csv')
    feas1=table('jssa/difficulty/start-feasibility-1023/per-problem-seed1.csv')
    byfull=defaultdict(list)
    for r in full:byfull[r['case_id']].append(r)
    alg={r['id']:r for r in algebra}; prec={r['id']:r for r in precision}
    feas=[{r['id']:r for r in z} for z in [feas0,feas1]]
    fragmented=[r for r in a if int(r['hits'])>=20 and int(r['hit_clusters_0.001'])>=10]
    rankdef={r['id'] for r in rank if int(r['nullity'])>0}
    non_voronoi=[r for r in a if r.get('nearest_destination_agreement') and float(r['nearest_destination_agreement'])<.5]
    selected=json.loads((OUT/'exploratory-summary.json').read_text())['near_inversion_candidates']
    ids={r['id'] for r in selected+non_voronoi+fragmented}
    joined=[]; zero=[]; census=[]; no_motion=[]
    for cid in sorted(r['id'] for r in a):
        d0=read(cid); d1=read(cid,1)
        if all(r['cls']!='hit' for r in d0['records']+d1['records']):zero.append(cid)
        x=np.array([r['x'] for r in d0['records']]);st=np.array([r['start'] for r in d0['records']])
        if np.allclose(x,st,rtol=0,atol=1e-10) and d0['counts'].get('hit',0)==len(x):no_motion.append(cid)
        if cid not in ids:continue
        fs=byfull[cid]; ag=alg.get(cid,{}); pr=prec.get(cid,{})
        row=dict(id=cid,full_correct=sum(r['correct']=='True' for r in fs),full_runs=len(fs),
                 full_median_seconds=float(np.median([float(r['wall_time_s']) for r in fs])),
                 full_sources=json.dumps(dict(Counter(r['final_answer_source'] for r in fs))),
                 full_median_refinement=float(np.median([float(r['refinement_time_s']) for r in fs])),
                 msolve_class=ag.get('msolve_class'),msolve_real_solutions=ag.get('real_solutions'),
                 polynomial_max_degree=ag.get('max_degree'),answer_degree=pr.get('degree'),
                 pslq_first_correct_grid=pr.get('first_correct_grid'),saved_80digit_count=pr.get('saved_80digit_count'))
        for seed,d in [(0,d0),(1,d1)]:
            q=feas[seed].get(cid,{}); nf=int(q.get('n_feas',0));ni=int(q.get('n_infeas',0))
            row[f'seed{seed}_p']=d['p_any'];row[f'seed{seed}_n']=len(d['records'])
            row[f'seed{seed}_p_feasible']=int(q['hit_feas'])/nf if nf else None
            row[f'seed{seed}_p_infeasible']=int(q['hit_infeas'])/ni if ni else None
        joined.append(row)
    for seed in [0,1]:
        cnt=Counter();ks=Counter();c=Counter();short=0;records=0;powell=[]
        for row in a:
            d=read(row['id'],seed);rs=d['records'];records+=len(rs);c.update(r['cls'] for r in rs)
            if len(rs)<200:short+=1
            for r in rs:ks.update(r.keys())
            if d['n_vars']>d['n_constraints']:powell.append(row['id'])
        census.append(dict(seed=seed,records=records,partial_problems=short,record_keys=dict(ks),class_counts=dict(c),powell_by_metadata=powell))
    cnts=[]
    for cid in ['AIME-2010-II-09','AIME-2015-II-07','HMMT-2022-FEB-GEO-01']:
        d=read(cid);w=np.diff(d['box']).ravel();x=np.array([r['x'] for r in d['records']])/w
        rr=next(r for r in a if r['id']==cid)
        cnts.append(dict(id=cid,clusters_e_4=rr['hit_clusters_0.0001'],clusters_e_3=rr['hit_clusters_0.001'],
            clusters_e_2=rr['hit_clusters_0.01'],start_clusters_seed1=len(cluster(starts(read(cid,1)),.001)[1]),
            start_clusters_seed1_are_not_observed_endpoint_clusters=True,
            max_seed0_start_end_move=float(np.max(np.abs(np.array([r['x'] for r in d['records']])-np.array([r['start'] for r in d['records']]))))))
    gmb=json.loads((ROOT/'jssa/results/gmb-success-definition/summary.json').read_text())
    s=dict(raw_census=census,full_runs=len(full),full_correct=sum(r['correct']=='True' for r in full),
        full_sources=dict(Counter(r['final_answer_source'] for r in full)),
        zero_hit_both_seeds=zero,zero_hit_full_3of3=[cid for cid in zero if sum(r['correct']=='True' for r in byfull[cid])==3],
        fragmented_problems=len(fragmented),fragmented_rankdef_overlap=sum(r['id'] in rankdef for r in fragmented),
        fragmented_msolve_classes=dict(Counter(alg.get(r['id'],{}).get('msolve_class','missing') for r in fragmented)),
        multibranch_eligible=sum(bool(r.get('nearest_destination_agreement')) for r in a),
        non_voronoi_majority=[r['id'] for r in non_voronoi],no_motion_full_success=no_motion,
        uniform_expected_clusters=1+199*.999**200,fragmentation_examples=cnts,
        gmb=[dict(record=r['record'],trials=r['trials'],returned=r['(a1)_models_returned'],
             indep_1e6=r['(b)_indep_1e-6_of_returned']) for r in gmb])
    write_csv('cross-source-audit.csv',joined)
    (OUT/'audit.json').write_text(json.dumps(s,ensure_ascii=False,indent=2))
    print(json.dumps(s,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
