"""Aggregate Q15 classifications and exploratory human-difficulty associations."""
from __future__ import annotations
import csv, gzip, hashlib, json, math, os
from collections import Counter, defaultdict
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
from scipy.stats import rankdata, spearmanr, pearsonr, mannwhitneyu, kruskal

HERE=Path(__file__).resolve().parent
LABELS=('a','b','c','d','e','unknown','no_failure')
PRIORITY=['e','c','d','a','b','unknown']

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x):return None
    return x

def dump(p,x):p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def writecsv(name,rows,fields=None):
    if not fields:fields=list(dict.fromkeys(k for r in rows for k in r))
    with (HERE/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(clean(rows))

def cause(counts):
    if not counts.get('failed_records',0):return 'no_failure'
    votes={k:counts.get('vote_'+k,0) for k in PRIORITY}
    maximum=max(votes.values())
    return next(k for k in PRIORITY if votes[k]==maximum)

def rates(total):
    D=total.get('finite_failed',0);F=total.get('failed_records',0)
    return {**total,**{f'{k}_pct_finite':100*total.get(k,0)/D if D else None for k in ('a','b','c','d','e','ab','a_and_b','vote_unknown')},
            'ab_pct_all_failed':100*total.get('ab',0)/F if F else None}

def compare(x,y):
    if not len(x) or not len(y):return None
    result=mannwhitneyu(x,y,alternative='two-sided',method='auto')
    return {'n_ab':len(x),'n_other':len(y),'median_ab':float(np.median(x)),
            'median_other':float(np.median(y)),'cliffs_delta':float(2*result.statistic/(len(x)*len(y))-1),
            'U':float(result.statistic),'p_exploratory':float(result.pvalue)}

def correlation(rows,xkey,ykey='human'):
    rr=[r for r in rows if r.get(xkey) is not None and r.get(ykey) is not None]
    if len(rr)<3:return {'n':len(rr),'rho':None}
    res=spearmanr([r[xkey] for r in rr],[r[ykey] for r in rr])
    return {'n':len(rr),'rho':float(res.statistic),'p_exploratory':float(res.pvalue)}

def human_analysis(rows):
    out={'exploratory':True,'n_problems':len(rows),'groups':[],'by_contest':{}}
    rr=[r for r in rows if r['human'] is not None]
    out['human_available']=len(rr);out['human_missing']=len(rows)-len(rr)
    for label in LABELS:
        r=[r for r in rows if r['main_cause']==label]
        values=[r['human'] for r in r if r['human'] is not None]
        out['groups'].append({'cause':label,'problems':len(r),'human_n':len(values),
            'median':float(np.median(values)) if values else None,
            'q25':float(np.quantile(values,.25)) if values else None,
            'q75':float(np.quantile(values,.75)) if values else None})
    measured=[r for r in rr if r['main_cause'] not in ('no_failure','unknown')]
    def contrast(rs):return compare([r['human'] for r in rs if r['main_cause'] in ('a','b')],[r['human'] for r in rs if r['main_cause'] not in ('a','b')])
    out['ab_vs_other_measured_failures']=contrast(measured)
    out['ab_vs_all_other_with_human']=contrast(rr)
    out['fraction_vs_human']=correlation(rr,'ab_fraction')
    groups=[[r['human'] for r in measured if r['main_cause']==c] for c in LABELS]
    usable=[g for g in groups if len(g)>=5]
    if len(usable)>=2:
        res=kruskal(*usable);out['kruskal']={'groups_at_least_5':[c for c,g in zip(LABELS,groups) if len(g)>=5],
            'H':float(res.statistic),'p_exploratory':float(res.pvalue)}
    for contest in sorted({r['contest'] for r in rr}):
        r=[r for r in rr if r['contest']==contest]
        out['by_contest'][contest]={'n':len(r),'fraction_vs_human':correlation(r,'ab_fraction'),
          'ab_vs_other':contrast([r for r in r if r['main_cause'] not in ('unknown','no_failure')])}
    rr=[r for r in rr if r['ab_fraction'] is not None]
    contests=sorted({r['contest'] for r in rr})
    X=np.column_stack([np.ones(len(rr)),rankdata([r['n_vars'] for r in rr]),
        rankdata([math.log1p(r['n_points']) for r in rr]),
        *[np.array([r['contest']==c for r in rr],float) for c in contests[1:]]])
    x=rankdata([r['ab_fraction'] for r in rr]);y=rankdata([r['human'] for r in rr])
    rx=x-X@np.linalg.lstsq(X,x,rcond=None)[0];ry=y-X@np.linalg.lstsq(X,y,rcond=None)[0]
    res=pearsonr(rx,ry)
    out['adjusted_rank_residual_correlation']={'n':len(rr),'rho':float(res.statistic),
        'controls':['contest','rank(n_vars)','rank(log1p(n_points))'],
        'note':'Descriptive partial rank correlation. No unadjusted Pearson p-value is interpreted as a partial test.'}
    return out

def main():
    files=sorted((HERE/'classified').glob('*.json'))
    results=[json.loads(p.read_text()) for p in files]
    manifest=json.loads((HERE/'input-manifest.json').read_text())
    errors=[r for r in results if r['status']!='ok'];ok=[r for r in results if r['status']=='ok']
    perproblem=[];source_totals=defaultdict(Counter);source_problems=Counter();sens=defaultdict(Counter)
    sens_causes=defaultdict(Counter);matches=[]
    for r in ok:
        for source,counts in r['source_stats'].items():
            source_totals[source].update(counts);source_problems[source]+=1
        primary=r['variants']['primary'].get('raw0/B',{})
        stats=r['source_stats']['raw0/B'];h=r['human'];meta=r['meta'];D=primary.get('finite_failed',0)
        row={'id':r['id'],'n_vars':meta['n_vars'],'n_points':meta['n_points'],
            'records':stats['records'],'hit':stats.get('hit',0),'failed_records':stats.get('failed_records',0),
            'finite_failed':D,'geometry_complete':stats.get('geometry_complete',0),'measurement_complete':stats.get('measurement_complete',0),
            'main_cause':cause(primary),'ab_fraction':primary.get('ab',0)/D if D else None,
            **{k:primary.get(k,0) for k in ('a','b','c','d','e','ab','a_and_b','vote_a','vote_b','vote_c','vote_d','vote_e','vote_unknown')},
            'p_saved':stats.get('hit',0)/stats['records'],
            'human':float(h['human']) if h.get('human') else None,'contest':h.get('contest'),
            'S0':meta['S0'],'hit_figures':meta['hit_figures'],'mask_reference':meta['mask_reference'],
            'pairs_excluded':meta['pairs_excluded'],'triples_excluded':meta['triples_excluded']}
        perproblem.append(row)
        for v,groups in r['variants'].items():
            for source,counts in groups.items():sens[(v,source)].update(counts)
            sens_causes[v][cause(groups.get('raw0/B',{}))]+=1
        b=r['basins']
        matches.append({'id':r['id'],'n_starts_match':int(b['n_starts'])==stats['records'],
            'p_match':abs(float(b['p'])-row['p_saved'])<1e-12})
    sources=[]
    for source,count in sorted(source_totals.items()):
        labels=sens[('primary',source)]
        sources.append({'source_arm':source,'problems':source_problems[source],**rates({**count,**labels})})
    sensitivity=[]
    for (v,source),ct in sorted(sens.items()):
        if source!='raw0/B':continue
        causes=sens_causes[v];prop=(causes['a']+causes['b'])/manifest['problems']
        row={'variant':v,**rates(ct),'main_ab_problems':causes['a']+causes['b'],
            'main_ab_pct_all_problems':100*prop,'main_causes':dict(causes)}
        row['stop_rule']=(ct['ab']/ct['finite_failed']<.15 and prop<.10)
        sensitivity.append(row)
    summary={'preregistration_sha256':manifest['preregistration_sha256'],'snapshot_finished_utc':manifest['finished_utc'],
       'expected_problems':manifest['problems'],'processed_problems':len(ok),'case_errors':errors,
       'primary':next(s for s in sources if s['source_arm']=='raw0/B'),
       'main_causes':dict(Counter(r['main_cause'] for r in perproblem)),
       'any_ab_problems':sum(r['ab']>0 for r in perproblem),
       'majority_ab_problems':sum(r['ab_fraction'] is not None and r['ab_fraction']>=.5 for r in perproblem),
       'ab_problem_weighted_mean':float(np.mean([r['ab_fraction'] for r in perproblem if r['ab_fraction'] is not None])),
       'sensitivity':sensitivity,'sources':sources,
       'mask_starts_only_problems':[r['id'] for r in perproblem if r['mask_reference']=='starts_only'],
       'initial_scale_fallback_problems':[r['id'] for r in ok if r['meta']['scale_fallback']],
       'basins_discrepancies':[r for r in matches if not(r['n_starts_match'] and r['p_match'])],
       'hit_control':dict(sum((Counter(r['hit_control']) for r in ok),Counter())),
       'evaluation_exceptions':dict(sum((Counter(r['errors']) for r in ok),Counter())),
       'local_searches_run':0,'classification_cpu_seconds':sum(r['seconds'] for r in results)}
    primary=next(r for r in sensitivity if r['variant']=='primary')
    conservative=next(r for r in sensitivity if r['variant']=='conservative_strict')
    summary['stop_rule']=primary['stop_rule']
    summary['mechanism_followup_decision']='中止' if primary['stop_rule'] else '続行' if primary['ab_pct_finite']>=25 and primary['main_ab_pct_all_problems']>=15 and not conservative['stop_rule'] else '縮小'
    human=human_analysis(perproblem)
    # Supplementary cross-tabs, residual evidence, and complete source overlap counts.
    patterns=Counter();byclass=defaultdict(Counter);subtypes=Counter();drows=[];examples=defaultdict(list)
    masks0=set(summary['mask_starts_only_problems']);mask_impact=Counter()
    for p in sorted((HERE/'classified').glob('*.jsonl.gz')):
        for line in gzip.decompress(p.read_bytes()).splitlines():
            row=json.loads(line)
            if row['source']!='raw0':continue
            patterns[''.join(k for k in 'abcd' if row.get(k)) or row['vote']]+=1
            ct=byclass[row['cls']];ct['failed']+=1;ct['finite']+=row['finite_x']
            for k in ('a','b','c','d','e','ab'):ct[k]+=bool(row.get(k))
            ct['unknown']+=row['vote']=='unknown'
            if row['finite_x']:
                def below(key,t):return row.get(key) is not None and row[key]<=t
                subtypes['pair']+=below('pair_ratio',1e-6)
                subtypes['area']+=below('area_ratio',1e-8)
                subtypes['radius']+=below('radius_ratio',1e-6)
                subtypes['collapse']+=below('diameter_over_S0',1e-6)
                subtypes['b_size']+=row.get('escape_ratio') is not None and row['escape_ratio']>=100
                subtypes['b_scale_probe']+=bool(row.get('scale_probe'))
                subtypes['b_scale_only']+=bool(row.get('scale_probe')) and not(row.get('escape_ratio') is not None and row['escape_ratio']>=100)
                for flag in ('a','b','ab','c'):
                    if row.get(flag):
                        subtypes[flag+'_residual_le_1e8']+=below('residual',1e-8)
                        subtypes[flag+'_residual_gt_1e8']+=row.get('residual') is not None and row['residual']>1e-8
                        if len(examples[flag])<10:examples[flag].append(row)
                if row['id'] in masks0:
                    mask_impact['finite_failed']+=1;mask_impact['ab']+=bool(row.get('ab'))
            if row.get('d') or row.get('d_unconfirmed'):drows.append(row)
    summary.update(patterns=dict(patterns),by_saved_class={k:dict(v) for k,v in byclass.items()},
                   subtypes=dict(subtypes),no_hit_mask_impact=dict(mask_impact))
    dump(HERE/'summary.json',summary);dump(HERE/'human-exploratory.json',human)
    dump(HERE/'branch-candidates.json',drows);dump(HERE/'examples.json',examples)
    writecsv('per-problem.csv',perproblem);writecsv('sources.csv',sources)
    writecsv('sensitivity.csv',[{k:v for k,v in r.items() if k!='main_causes'} for r in sensitivity])
    writecsv('human-by-cause.csv',human['groups'])
    writecsv('class-cross-tab.csv',[{'saved_class':k,**v} for k,v in byclass.items()])
    print(json.dumps(clean({'processed':len(ok),'errors':errors,'primary':summary['primary'],'main_causes':summary['main_causes'],
      'stop':summary['stop_rule'],'followup':summary['mechanism_followup_decision'],'human':human}),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
