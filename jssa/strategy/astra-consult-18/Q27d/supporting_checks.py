"""Secondary source audit. All computations are descriptive and retrospective."""
import json
from collections import Counter
from explore import ROOT, OUT, table, read_bytes, write_csv, dump, avg, median, manifest

def main():
    rows=table('jssa/strategy/astra-consult-18/Q27d/census-both-seeds.csv')
    byid={r['id']:r for r in rows}
    published=table('jssa/difficulty/minima/basins-323.csv')
    disagreement=[r['id'] for r in published if r['id'] in byid and abs(r['p']-byid[r['id']]['p'])>1e-12]
    conditions=table('jssa/strategy/astra-consult-18/q21e-phase-transition/competition-census.csv')
    condition_bands={}
    for key in ['n_eq','n_constraints_native','dsl_eq_count']:
        sub=[r for r in conditions if r['d'] and 1.75<=(r[key] or 0)/r['d']<2]
        condition_bands[key]={'ids':[r['id'] for r in sub], 'n':len(sub),
             'p0':avg([byid[r['id']]['p'] for r in sub]),'p1':avg([byid[r['id']]['p1'] for r in sub])}
    expansion=table('jssa/strategy/astra-consult-18/Q27d/expansion.csv')
    old_again=table('jssa/strategy/astra-consult-12/C/primary_results.csv')
    interventions=json.loads(read_bytes('jssa/strategy/astra-consult-12/C/interventions.json'))
    exp={'problems':len(expansion),'positive':sum(r['deltaY']>0 for r in expansion),
         'gt_point2':sum(r['deltaY']>.2 for r in expansion),
         'negative':sum(r['deltaY']<0 for r in expansion),'tie':sum(r['deltaY']==0 for r in expansion),
         'N_min':min(r['N'] for r in expansion),'N_max':max(r['N'] for r in expansion),
         'mean_delta':avg([r['deltaY'] for r in expansion]),
         'median_delta':median([r['deltaY'] for r in expansion]),
         'prior_independent_seed':102301,'prior_selected_results':old_again,'interventions':interventions}
    stages=table('jssa/results/stage-profile-20261023/per-case.csv')
    zero={r['id'] for r in rows if r['h']==0}
    bz=[r for r in rows if r['h']==0 and r['h1']==0]
    high=[r for r in rows if r['d'] in [6,7]]
    source=Counter((r['final_answer_source'],r['correct']) for r in stages if r['case_id'] in zero)
    zeros={'both_zero_problems':len(bz),'both_zero_full_any':sum(r['full_correct']>0 for r in bz),
        'both_zero_full_correct':sum(r['full_correct'] for r in bz),'both_zero_full_runs':sum(r['full_runs'] for r in bz),
        'high_d_6_7_n':len(high),'high_d_p0':avg([r['p'] for r in high]),'high_d_p1':avg([r['p1'] for r in high]),
        'high_d_full_correct':sum(r['full_correct'] for r in high),'high_d_full_runs':sum(r['full_runs'] for r in high),
        'zero_source_counts':[{'source':s,'correct':c,'n':n} for (s,c),n in sorted(source.items())]}
    degree=[]
    for k in ['degree','max_degree']:
        for v in sorted({r[k] for r in rows if r[k] is not None}):
            rs=[r for r in rows if r[k]==v]
            degree.append({'kind':k,'degree':v,'n':len(rs),'p0':avg([r['p'] for r in rs]),'p1':avg([r['p1'] for r in rs]),
                          'd_mean':avg([r['d'] for r in rs]),'identify_s_median':median([r['identify_s'] for r in rs])})
    write_csv('degree-replay.csv',degree)
    real_root_groups=[]
    solved=[r for r in rows if r['msolve_class']=='answer_set_matches']
    for label,predicate in [('1-2',lambda x:1<=x<=2),('3-8',lambda x:3<=x<=8),('9+',lambda x:x>=9)]:
        sub=[r for r in solved if r['real_solutions'] is not None and predicate(r['real_solutions'])]
        real_root_groups.append({'real_solutions':label,'n':len(sub),'d_mean':avg([r['d'] for r in sub]),
                                 'p0':avg([r['p'] for r in sub]),'p1':avg([r['p1'] for r in sub])})
    write_csv('real-root-counts.csv',real_root_groups)
    small=[r for r in rows if r['d']<=2 and r['large_poly']]
    exact_reverse={'small_d_large_poly_n':len(small),'p0_mean':avg([r['p'] for r in small]),
          'p1_mean':avg([r['p1'] for r in small]),'full_all3':sum(r['full_correct']==3 for r in small),
          'msolve_matches':sum(r['msolve_class']=='answer_set_matches' for r in small)}
    gmb=table('jssa/results/gmb-success-definition/per-trial.csv')
    gmb_stats=[]
    for setting in ['default','strict']:
        sub=[r for r in gmb if str(r['record']).startswith(setting)]
        gmb_stats.append({'setting':setting,'saved_scored_outputs':len(sub),'unique_problems':len({r['case_id'] for r in sub}),
                         'indep_1e-3':sum(r['indep_1e-3'] for r in sub),
                         'indep_1e-6':sum(r['indep_1e-6'] for r in sub),'indep_1e-9':sum(r['indep_1e-9'] for r in sub)})
    precision=table('jssa/difficulty/multiplicity/per-case.csv')
    pslq=table('jssa/strategy/astra-consult-18/q21b-number-theory/problem-summary.csv')
    precision_out={'selected_problems':len(precision),'original_pass_cases':sum(bool(r['O_pass']) for r in precision),
                   'original_best_digits_median':median([r['O_best_digits'] for r in precision]),
                   'pslq_problems':len(pslq),'pslq_algebraic_problems':sum(r['has_pi'] is False for r in pslq),
                   'first_correct_grid_le80':sum(r['first_correct_grid'] is not None and r['first_correct_grid']<=80 for r in pslq)}
    # Audit all source files used for externally reported comparisons.
    for rel in ['benchmarks/extra-variables/PROTOCOL.md','jssa/draft/supplement-v10.md',
                'jssa/strategy/astra-consult-12/C/answer.md',
                'jssa/strategy/astra-consult-18/q21e-phase-transition/answer.md',
                'benchmarks/gmb_comparison/README.md','jssa/results/gmb-success-definition/README.md']:
        read_bytes(rel)
    out={'published_basin_p_disagreements':disagreement,'condition_bands':condition_bands,
         'expansion':exp,'zero_hit':zeros,'polynomial_size':exact_reverse,'real_root_groups':real_root_groups,'gmb':gmb_stats,'precision':precision_out,
         'missing_local_primary_sources':['jssa/difficulty/minima/basins-extra60.csv','jssa/difficulty/minima/raw-extra60',
                    'jssa/results/difficulty-20261022/extra-variables-campaign/']}
    dump('supporting-checks.json',out);dump('supporting-manifest.json',manifest)
    print(json.dumps({k:v for k,v in out.items() if k!='expansion'}))
    print('EXPANSION',json.dumps({k:v for k,v in exp.items() if k not in ['prior_selected_results','interventions']}))

if __name__=='__main__': main()
