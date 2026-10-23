"""Analyze every frozen start; no optimization, no input or threshold changes."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

OUT=Path(__file__).resolve().parent


def dump(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n")


def csv_write(name,rows):
    with (OUT/name).open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def wilson(k,n):
    z=1.959963984540054
    p=k/n
    cen=(p+z*z/(2*n))/(1+z*z/n)
    rad=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0,cen-rad),min(1,cen+rad)]


def comparison(records,a,b,rng):
    ra,rb=records[a],records[b]
    assert set(ra)==set(rb)
    keys=sorted(ra)
    aa=np.array([ra[k]["hit"] for k in keys],dtype=int)
    bb=np.array([rb[k]["hit"] for k in keys],dtype=int)
    dd=aa-bb
    assert all(ra[k]["start"]==rb[k]["start"] for k in keys)
    gain,loss=int(sum(dd==1)),int(sum(dd==-1))
    bs=dd[rng.integers(0,len(keys),size=(10000,len(keys)))].mean(axis=1)
    return {"a":a,"b":b,"n":len(keys),"a_hits":int(aa.sum()),"b_hits":int(bb.sum()),
            "delta":float(dd.mean()),"gain":gain,"loss":loss,"same":len(keys)-gain-loss,
            "delta_ci_low":float(np.quantile(bs,.025)),"delta_ci_high":float(np.quantile(bs,.975)),
            "p_one_sided":float(binomtest(gain,gain+loss,.5,alternative="greater").pvalue) if gain+loss else 1.0}


def main():
    pairs=json.loads((OUT/'stimuli.json').read_text())
    lock=json.loads((OUT/'registration-lock.json').read_text())
    hashes={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest()==v for n,v in lock['files'].items()}
    assert all(hashes.values())
    rng=np.random.default_rng(220299)
    modes=[]; contrasts=[]; details=[]; stationarity=[]; h_matches=[]
    errors=Counter(); stops=Counter(); all_rows=[]
    for pair in pairs:
        raw=json.loads((OUT/'raw'/f"{pair['id']}.json").read_text())
        rs={}
        for r in raw['rows']:
            key=(r['seed'],r['k'])
            assert key not in rs.setdefault(r['mode'],{})
            rs[r['mode']][key]=r
            if 'error' in r: errors[r['error']]+=1
            stops[(r['mode'],str(r.get('stop',{}).get('status')))]+=1
        all_rows += raw['rows']
        for mode, records in rs.items():
            n=len(records); assert n==64
            hits=sum(r['hit'] for r in records.values())
            ci=wilson(hits,n)
            modes.append({'pair':pair['id'],'mode':mode,'n':n,'hits':hits,'p':hits/n,'wilson_low':ci[0],'wilson_high':ci[1],
                          'geometry_hits':sum(r['geometry_hit'] for r in records.values()),
                          'errors':sum('error' in r for r in records.values()),
                          'median_evaluations':float(np.median([r.get('telemetry_evaluations',0) for r in records.values()]))})
        if pair['group']=='S':
            mainc=comparison(rs,'power_near','power_far',rng)
            enc=comparison(rs,'power_near','length_near',rng)
            lng=comparison(rs,'long_near','long_far',rng)
            dn=comparison(rs,'power_near','direct_near',rng)
            df=comparison(rs,'power_far','direct_far',rng)
            for kind,c in [('S_main',mainc),('S_encoding',enc),('S_long',lng),('S_direct_near',dn),('S_direct_far',df)]:
                contrasts.append({'pair':pair['id'],'kind':kind,**c})
            counts={m:sum(r['hit'] for r in records.values()) for m,records in rs.items()}
            details.append({'pair':pair['id'],'a':pair['a'],'h':pair['h'],**counts,
                            'main_delta':mainc['delta'],'main_pass':mainc['a_hits']-mainc['b_hits']>=13,
                            'encoding_delta':enc['delta'],'encoding_pass':enc['a_hits']-enc['b_hits']>=13,
                            'near_high_pass':mainc['a_hits']>=61,'long_pass':lng['a_hits']-lng['b_hits']>=13,
                            'direct_pass':max(abs(dn['delta']),abs(df['delta']))<=.05 and min(dn['same'],df['same'])>=61})
            a,h=float(pair['a']),float(pair['h'])
            far_min=(3*(h+1)+math.sqrt(9+6*h-15*h*h))/6
            for r in rs['power_far'].values():
                if r['hit'] or 'x' not in r: continue
                x,y=r['x']; s=-1
                residuals=np.array([(x+a)**2+y*y-a*a-1,(x-a)**2+y*y-a*a-1,x*x+(y-h)**2-(s-h)**2])
                J=np.array([[2*(x+a),2*y],[2*(x-a),2*y],[2*x,2*(y-h)]])
                gradient=2*J.T@residuals
                hessian=2*J.T@J+4*residuals.sum()*np.eye(2)
                distance=math.hypot(x,y-far_min)
                stationarity.append({'pair':pair['id'],'seed':r['seed'],'k':r['k'],
                    'expected_min_y':far_min,'endpoint_distance_to_min':distance,
                    'gradient_norm':float(np.linalg.norm(gradient)),
                    'hessian_min_eigenvalue':float(np.linalg.eigvalsh(hessian)[0]),
                    'residual_norm':float(np.linalg.norm(residuals)),'matches_theory_1e_5':distance<=1e-5,
                    'endpoint_is_positive_residual':float(np.linalg.norm(residuals))>1e-8})
        else:
            c=comparison(rs,'easy','hard',rng)
            contrasts.append({'pair':pair['id'],'kind':'H_main',**c})
            maxdist=max(math.dist(rs['easy'][k]['x'],rs['hard'][k]['x']) for k in rs['easy'])
            exact=sum(rs['easy'][k]['x']==rs['hard'][k]['x'] for k in rs['easy'])
            gm=sum(rs['easy'][k]['geometry_hit']==rs['hard'][k]['geometry_hit'] for k in rs['easy'])
            evaluations_equal=sum(rs['easy'][k]['telemetry_evaluations']==rs['hard'][k]['telemetry_evaluations'] for k in rs['easy'])
            h_matches.append({'pair':pair['id'],'family':pair['family'],'easy_hits':c['a_hits'],'hard_hits':c['b_hits'],
                              'delta':c['delta'],'machine_pass':abs(c['delta'])<=.05,
                              'identical_endpoints':exact,'maximum_endpoint_distance':maxdist,
                              'geometry_labels_same':gm,'evaluation_counts_same':evaluations_equal,
                              'human_difference':'unmeasured'})
    primary=[c for c in contrasts if c['kind']=='S_main']
    order=sorted(range(len(primary)),key=lambda i:primary[i]['p_one_sided'])
    prev=0.0
    for rank,i in enumerate(order):
        prev=max(prev,min(1.0,(len(primary)-rank)*primary[i]['p_one_sided']))
        primary[i]['p_holm_primary']=prev
    for c in contrasts: c.setdefault('p_holm_primary','')
    csv_write('per-mode.csv',modes)
    csv_write('contrasts.csv',contrasts)
    csv_write('S-all-pairs.csv',details)
    csv_write('H-all-pairs.csv',h_matches)
    csv_write('power-far-stationarity.csv',stationarity)
    summary={'total_rows':len(all_rows),'main_rows':sum(r['mode'] not in {'direct_near','direct_far','long_near','long_far'} for r in all_rows),
             'errors':dict(errors),'registration_hashes_match':hashes,
             'S_main_pairs_pass':sum(r['main_pass'] for r in details),'S_main_mean_difference':float(np.mean([r['main_delta'] for r in details])),
             'S_main_pass':sum(r['main_pass'] for r in details)>=7 and np.mean([r['main_delta'] for r in details])>=.20,
             'S_near_high_pass_count':sum(r['near_high_pass'] for r in details),
             'S_encoding_pairs_pass':sum(r['encoding_pass'] for r in details),'S_encoding_pass':sum(r['encoding_pass'] for r in details)>=7,
             'S_encoding_misses':[r['pair'] for r in details if not r['encoding_pass']],
             'S_long_pairs_pass':sum(r['long_pass'] for r in details),'S_long_pass':sum(r['long_pass'] for r in details)>=7,
             'S_direct_pairs_pass':sum(r['direct_pass'] for r in details),'S_direct_pass':sum(r['direct_pass'] for r in details)>=9,
             'H_machine_pairs_pass':sum(r['machine_pass'] for r in h_matches),'H_machine_pass':sum(r['machine_pass'] for r in h_matches)>=9,
             'H_identical_endpoints':sum(r['identical_endpoints'] for r in h_matches),
             'H_geometry_labels_same':sum(r['geometry_labels_same'] for r in h_matches),
             'H_evaluation_counts_same':sum(r['evaluation_counts_same'] for r in h_matches),
             'H_human_difficulty_observed_pairs':0,'double_dissociation_established':False,
             'S_far_failures':len(stationarity),'S_far_failures_match_minimum':sum(r['matches_theory_1e_5'] for r in stationarity),
             'S_far_max_min_distance':max(r['endpoint_distance_to_min'] for r in stationarity),
             'S_far_min_Hessian_eigenvalue':min(r['hessian_min_eigenvalue'] for r in stationarity),
             'S_far_residual_range':[min(r['residual_norm'] for r in stationarity),max(r['residual_norm'] for r in stationarity)]}
    # Convert NumPy Boolean scalars explicitly for strict JSON.
    summary={k:bool(v) if isinstance(v,np.bool_) else v for k,v in summary.items()}
    dump('summary.json',summary)
    dump('stopping-status.json',[{'mode':m,'status':s,'count':n} for (m,s),n in sorted(stops.items())])
    dump('failed-H-starts.json',[r for r in all_rows if r['pair'].startswith('H') and not r['hit']])
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
