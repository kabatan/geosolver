"""Fixed Q40a comparisons, with failures retained in every denominator."""
from common import *
from collections import Counter, defaultdict
import csv
import sqlite3
import numpy as np
from scipy.stats import rankdata

UNKNOWN = {'unstarted','started','local_done','local_timeout','outer_timeout','worker_abnormal','scoring_exception'}


def csv_write(path, rows):
    columns=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns); writer.writeheader(); writer.writerows(rows)


def bootstrap(deltas, selected):
    # Every delta is an integer number of thousandths. Keep boundary decisions exact.
    draws=np.zeros(10000,dtype=np.int64)
    for group in ('development','unseen'):
        values=np.array([round(1000*deltas[r['canonical_id']]) for r in selected if r['cohort']==group],dtype=np.int64)
        assert len(values)==20
        for r in range(10000):
            indices=[int(sha(f'Q40|4040|bootstrap|{r}|{group}|{j}'.encode()),16)%20 for j in range(20)]
            draws[r]+=sum(values[indices])
    draws.sort()
    return [int(draws[249])/40000,int(draws[9749])/40000]


def correlations(rows):
    if len(rows)<20:
        return {'n':len(rows),'spearman':None,'partial_rank':None,'reason':'fewer than 20 complete problems'}
    x=rankdata([r[0] for r in rows]); y=rankdata([r[1] for r in rows])
    if np.ptp(x)==0 or np.ptp(y)==0:
        return {'n':len(rows),'spearman':None,'partial_rank':None,'reason':'constant ranks'}
    controls=np.column_stack([np.ones(len(rows)),[r[2] for r in rows],rankdata([r[3] for r in rows])])
    xr=x-controls@np.linalg.lstsq(controls,x,rcond=None)[0]
    yr=y-controls@np.linalg.lstsq(controls,y,rcond=None)[0]
    partial=None if np.linalg.norm(xr)<1e-12 or np.linalg.norm(yr)<1e-12 else float(np.corrcoef(xr,yr)[0,1])
    return {'n':len(rows),'spearman':float(np.corrcoef(x,y)[0,1]),'partial_rank':partial,
            'reason':None if partial is not None else 'constant ranks after control regression'}


def analyze():
    verify_source()
    selected=read(PLAN/'selected.json'); ids=[r['canonical_id'] for r in selected]
    db=sqlite3.connect(f'file:{EXTERNAL}/trials.sqlite?mode=ro',uri=True)
    statuses=dict(db.execute('SELECT status,count(*) FROM trials GROUP BY status'))
    assert sum(statuses.values())==144000
    assert not any(statuses.get(s,0) for s in ('unstarted','started','local_done')), 'Do not report an unfinished plan as complete'
    builds={(cid,v):dict(json.loads(d),status=s) for cid,v,s,d in db.execute('SELECT case_id,variant,status,data FROM builds')}
    diagnostics={}
    for cid in ids:
        folder=EXTERNAL/'diagnostics'/cid
        diagnostics[cid]={'scale':read(folder/'scale.json'),**{v:read(folder/(v+'.json')) for v in VARIANTS}}
    conditions=[]; index={}; methods=Counter(); actual_calls=0; status_by_seed=defaultdict(Counter)
    for case in selected:
        cid=case['canonical_id']; d=diagnostics[cid]['scale']['d']
        for seed in SEEDS:
            for variant in VARIANTS:
                raw=db.execute('SELECT k,position,status,data FROM trials WHERE case_id=? AND seed=? AND variant=? ORDER BY k',(cid,seed,variant)).fetchall()
                assert [r[0] for r in raw]==list(range(200)), (cid,seed,variant)
                counts=Counter(); unknown=0; method=builds.get((cid,variant),{}).get('method','unavailable')
                for k,position,status,data in raw:
                    record=json.loads(data); status_by_seed[seed][status]+=1
                    if record.get('attempted'):
                        methods[record['method']]+=1; actual_calls+=1
                    if status in UNKNOWN or (status=='build_failed' and any(word in json.dumps(record.get('reason',{})).lower() for word in ('timeout','interrupted','worker_abnormal'))): unknown+=1
                    # Recalculate the acceptance gate from saved endpoint measurements.
                    endpoint=record.get('endpoint'); F=record.get('F')
                    eligible=bool(status=='returned' and endpoint is not None and F is not None
                        and all(x is not None and math.isfinite(x) for x in endpoint+F)
                        and record.get('evaluation_status')=='ok' and record.get('guard_ok') is True
                        and record.get('hard_feasible') is True and record.get('in_box') is True)
                    norm=math.hypot(*F) if eligible else math.inf
                    assert bool(record.get('hit'))==(eligible and norm<=1e-8), (cid,seed,k,variant,'saved acceptance disagreement')
                    for label,threshold in (('strict',1e-10),('primary',1e-8),('loose',1e-6)):
                        counts[label]+=int(eligible and norm<=threshold)
                    if d is not None and eligible:
                        assert len(d)==len(F)
                        counts['scaled']+=int(math.hypot(*(f/sc for f,sc in zip(F,d,strict=True)))<=1e-8)
                row={'case_id':cid,'cohort':case['cohort'],'seed':seed,'variant':variant,
                     'n_vars':case['n_vars'],'method':method,'denominator':200,
                     'hits':counts['primary'],'p':counts['primary']/200,'strict_hits':counts['strict'],'strict_p':counts['strict']/200,
                     'loose_hits':counts['loose'],'loose_p':counts['loose']/200,
                     'scaled_hits':counts['scaled'] if d is not None else None,'scaled_p':counts['scaled']/200 if d is not None else None,
                     'unknown':unknown,'p_lower':counts['primary']/200,'p_upper':(counts['primary']+unknown)/200}
                ref=diagnostics[cid][variant].get('references',{}).get(str(seed),{}).get('jacobian',{})
                row.update(sigma_valid=bool(ref.get('valid')),sigma_min=ref.get('sigma_min'),rank=ref.get('rank'),
                           sigma_ratio=ref.get('scaled_ratio',[None,None])[1] if ref.get('valid') else None)
                conditions.append(row); index[cid,seed,variant]=row
    db.close()
    problems=[]; deltas={s:{} for s in SEEDS}; primary_nums={s:{} for s in SEEDS}
    coverage3=[]; coverage4=[]; support3=[]; support4=[]
    for case in selected:
        cid=case['canonical_id']; row={'case_id':cid,'cohort':case['cohort'],'n_vars':case['n_vars']}
        for seed in SEEDS:
            base=index[cid,seed,'original']; pert=[index[cid,seed,v] for v in VARIANTS[1:]]
            numerator=sum(r['hits'] for r in pert)-5*base['hits']
            primary_nums[seed][cid]=numerator; deltas[seed][cid]=numerator/1000
            row[f'original_p_{seed}']=base['p']; row[f'delta_{seed}']=numerator/1000
            row[f'improved_{seed}']=numerator>=50; row[f'worsened_{seed}']=numerator<=-50
            row[f'delta_lower_{seed}']=(numerator-5*base['unknown'])/1000
            row[f'delta_upper_{seed}']=(numerator+sum(r['unknown'] for r in pert))/1000
            for label in ('strict','loose','scaled'):
                values=[r[label+'_hits'] for r in pert]+[base[label+'_hits']]
                row[f'delta_{label}_{seed}']=None if any(v is None for v in values) else (sum(values[:5])-5*values[5])/1000
            for level,variants in (('e3',('e3_plus','e3_minus')),('e2',('e2_plus','e2_minus')),('e1',('e1_random',))):
                row[f'delta_{level}_{seed}']=(sum(index[cid,seed,v]['hits'] for v in variants)-len(variants)*base['hits'])/(200*len(variants))
        stable=all(primary_nums[s][cid]>=50 for s in SEEDS); row['stable_improvement']=stable
        sv={}
        for v in ('original','e2_plus','e2_minus'):
            values=[index[cid,s,v]['sigma_min'] for s in SEEDS]
            sv[v]=None if any(x is None for x in values) else float(np.median(values))
            row['S_'+v]=sv[v]
        valid3=all(v is not None for v in sv.values())
        row['G']=((math.log10(sv['e2_plus']+1e-12)+math.log10(sv['e2_minus']+1e-12))/2-math.log10(sv['original']+1e-12)) if valid3 else None
        row['P3_support']=bool(valid3 and stable and row['G']>=math.log10(2))
        if valid3: coverage3.append(cid)
        if row['P3_support']: support3.append(cid)
        branch_good=[]; all_b_valid=True
        for eps in ('0.0001','1e-05','0.001'):
            bs={v:diagnostics[cid][v].get('branch',{}).get(eps,{}).get('B') for v in ('original','e2_plus','e2_minus')}
            valid=all(b is not None for b in bs.values()); all_b_valid &= valid
            branch_good.append(valid and bs['e2_plus']>=2*bs['original'] and bs['e2_minus']>=2*bs['original'])
            for v,b in bs.items(): row[f'B_{eps}_{v}']=b
        row['P4_support']=bool(stable and all(branch_good))
        if all_b_valid: coverage4.append(cid)
        if row['P4_support']: support4.append(cid)
        problems.append(row)
    by_id={r['case_id']:r for r in problems}
    seed_summary={}
    for seed in SEEDS:
        per_group={}
        for group in ('development','unseen'):
            members=[r['canonical_id'] for r in selected if r['cohort']==group]
            per_group[group]={'D':sum(primary_nums[seed][cid] for cid in members)/20000,
                              'improved':sum(primary_nums[seed][cid]>=50 for cid in members),
                              'worsened':sum(primary_nums[seed][cid]<=-50 for cid in members),'denominator':20}
        summary={'D':sum(primary_nums[seed].values())/40000,'improved':sum(v>=50 for v in primary_nums[seed].values()),
                 'worsened':sum(v<=-50 for v in primary_nums[seed].values()),'groups':per_group,
                 'D_lower':sum(round(1000*r[f'delta_lower_{seed}']) for r in problems)/40000,
                 'D_upper':sum(round(1000*r[f'delta_upper_{seed}']) for r in problems)/40000,
                 'statuses':dict(status_by_seed[seed]),'planned_trials':48000}
        for label in ('strict','loose','scaled'):
            values=[r[f'delta_{label}_{seed}'] for r in problems]
            summary['D_'+label]=None if any(v is None for v in values) else sum(round(1000*v) for v in values)/40000
        summary['sign_reversal']=any(summary['D']*summary['D_'+label]<0 for label in ('strict','loose','scaled') if summary['D_'+label] is not None)
        seed_summary[str(seed)]=summary
    stable_ids=[r['case_id'] for r in problems if r['stable_improvement']]
    def group_counts(members):
        return {g:sum(cid in members for cid in ids if by_id[cid]['cohort']==g) for g in ('development','unseen')}
    stable_groups=group_counts(stable_ids); groups3=group_counts(support3); groups4=group_counts(support4)
    primary=seed_summary['404001']; interval=bootstrap(deltas[404001],selected)
    w=primary['improved']; tail=sum(math.comb(40,k) for k in range(w,41))/2**40
    p1=primary['D']>=.05 and interval[0]>0 and w>=26
    p2=(len(stable_ids)>=20 and min(stable_groups.values())>=8 and
        all(s['D']>=.04 and s['groups']['unseen']['D']>=.03 for s in seed_summary.values()))
    p3=len(coverage3)>=24 and len(support3)>=10 and min(groups3.values())>=3
    p4=len(support4)>=4 and min(groups4.values())>=1
    feasible_original=sum(any(index[cid,s,'original']['hits']>0 for s in SEEDS) for cid in ids)
    feasible_changed=sum(any(index[cid,s,v]['hits']>0 for s in SEEDS) for cid in ids for v in VARIANTS[1:])
    sign_reversal=any(s['sign_reversal'] for s in seed_summary.values())
    correlations_by_seed={str(s):correlations([(index[cid,s,'original']['sigma_ratio'],deltas[s][cid],int(by_id[cid]['cohort']=='unseen'),by_id[cid]['n_vars'])
                         for cid in ids if index[cid,s,'original']['sigma_ratio'] is not None]) for s in SEEDS}
    subgroup_rows=[]
    for s in SEEDS:
        groups=[('all','all',ids)]
        for g in ('development','unseen'): groups.append(('cohort',g,[cid for cid in ids if by_id[cid]['cohort']==g]))
        for label in ('2-3','4+'):
            groups.append(('n_vars',label,[cid for cid in ids if (by_id[cid]['n_vars']<=3)==(label=='2-3')]))
        for method in ('LM','Powell'):
            groups.append(('method',method,[cid for cid in ids if index[cid,s,'original']['method']==method]))
        for label in ('p=0','0<p<1','p=1'):
            groups.append(('original_p',label,[cid for cid in ids if ('p=0' if index[cid,s,'original']['p']==0 else 'p=1' if index[cid,s,'original']['p']==1 else '0<p<1')==label]))
        for axis,label,members in groups:
            subgroup_rows.append({'seed':s,'axis':axis,'group':label,'n':len(members),
                                 'D':sum(primary_nums[s][cid] for cid in members)/(1000*len(members)) if members else None,
                                 'improved':sum(primary_nums[s][cid]>=50 for cid in members),
                                 'worsened':sum(primary_nums[s][cid]<=-50 for cid in members)})
    summary={'complete':True,'planned_trials':144000,'primary_trials':48000,'replication_trials':96000,
             'actual_local_calls':actual_calls,'statuses':statuses,'local_methods':dict(methods),
             'seed_summary':seed_summary,'primary_D_95_interval':interval,'primary_one_sided_binomial_tail':tail,
             'stable_improvement_ids':stable_ids,'stable_groups':stable_groups,
             'P1':{'supported':bool(p1),'direction_refuted':primary['D']<=0},
             'P2':{'supported':bool(p2),'stable_count':len(stable_ids),'groups':stable_groups},
             'P3':{'supported':bool(p3),'assessable':len(coverage3)>=24,'coverage':len(coverage3),'support_count':len(support3),'support_ids':support3,'groups':groups3},
             'P4':{'supported':bool(p4),'coverage_all_widths':len(coverage4),'support_count':len(support4),'support_ids':support4,'groups':groups4},
             'feasibility':{'original_cases_with_hit':feasible_original,'changed_variants_with_hit':feasible_changed,
                            'passes_registered_gate':feasible_original>=32 and feasible_changed>=160},
             'precision_scale_sign_reversal':sign_reversal,
             'censoring_separated':primary['D_lower']>0,
             'correlations':correlations_by_seed,'source_hash':SOURCE_HASH,
             'prediction_lock_sha256':sha((PLAN/'prediction.lock.json').read_bytes()),'at_utc':utc()}
    csv_write(HERE/'per-condition.csv',conditions); csv_write(HERE/'per-problem.csv',problems); csv_write(HERE/'subgroups.csv',subgroup_rows)
    write(HERE/'summary.json',summary)
    g=stable_groups; s2=seed_summary['404002']; s3=seed_summary['404003']
    supported_effect='あり（P1を支持）' if p1 else '確認できず（P1を支持しない）'
    central='保留。局所探索での数値摂動の効果まで。' if p1 else '不可。主予言が成立しなかった。'
    rows=[
        '①直感に反するか：'+supported_effect+'。',
        '②深い理論が必要か：未確認。特異点や枝の合流の証明はしていない。',
        f'③広く再現するか：全3seedで改善は{len(stable_ids)}/40。開発{g["development"]}/20（測定20/323、適格188/323）、未使用出自{g["unseen"]}/20（測定20/54）。'+('P2を支持。' if p2 else 'P2を支持しない。'),
        '④solverならではか：未確認。他手法との直接比較はしていない。',
        '人間が導けるか：特異な条件が数値計算を難しくするという定性的予想は可能。問題別の量的予測は未確認。',
        '他手法でも得られるか：起こり得るが、今回は未比較。',
        'Aの中心を担えるか：'+central,
        '',
        '| 予言 | 固定した支持条件（要約） | 観測 | 判定 |',
        '|---|---|---|---|',
        f'| P1 改善が多い | D≥0.05、95%区間下端>0、改善≥26/40 | D={primary["D"]:+.5f}、区間[{interval[0]:+.5f}, {interval[1]:+.5f}]、改善{w}/40・悪化{primary["worsened"]}/40 | '+('支持' if p1 else '方向も反証' if primary['D']<=0 else '未支持')+' |',
        f'| P2 群・seedを越える | 安定≥20/40、各群≥8/20、各seed D≥0.04・未使用群D≥0.03 | 安定{len(stable_ids)}/40（開発{g["development"]}、未使用出自{g["unseen"]}） | '+('支持' if p2 else '未支持')+' |',
        f'| P3 特異性が緩む | 安定改善とσmin 2倍が≥10/40、各群≥3、診断≥24/40 | 該当{len(support3)}/40、診断{len(coverage3)}/40 | '+('支持' if p3 else '判定不可' if len(coverage3)<24 else '未支持')+' |',
        f'| P4 観測枝が離れる | 安定改善とB 2倍が≥4/40、各群≥1、3クラスタ幅で成立 | 該当{len(support4)}/40、必要診断完備{len(coverage4)}/40 | '+('支持' if p4 else '未支持')+' |',
        '',
        f'seed 404001/404002/404003の改善数は{w}/{s2["improved"]}/{s3["improved"]}（各40問）、Dは{primary["D"]:+.5f}/{s2["D"]:+.5f}/{s3["D"]:+.5f}。主seedの片側二項尾確率は{tail:.6g}。',
        f'予定144,000枠（主48,000・再現96,000）を処理。実際の局所呼出し{actual_calls:,}回（LM {methods["LM"]:,}、Powell {methods["Powell"]:,}）。失敗も各条件200・全体40問の分母に残した。',
        f'図が1個以上得られたのは元版{feasible_original}/40、変更版{feasible_changed}/200。'+('可解性の事前基準を満たす。' if feasible_original>=32 and feasible_changed>=160 else '可解性の事前基準を満たさず、「一般位置化で楽になる」という説明は不可。'),
        f'打切りを最悪側に扱った主seedのD下限は{primary["D_lower"]:+.5f}。'+('打切りだけでは効果の向きは変わらない。' if primary['D_lower']>0 else '打切りとの切分けは未了。'),
        '精度・尺度の感度確認：'+('主効果の符号反転があり、機構説明は不可。' if sign_reversal else '算出できた条件では主効果の符号反転なし。尺度欠測は補完していない。'),
        '',
        '失敗内訳・全版全seedのp・水準別Δ・特異値・相関は [summary.json](stage2/summary.json)、[per-condition.csv](stage2/per-condition.csv)、[per-problem.csv](stage2/per-problem.csv)、[subgroups.csv](stage2/subgroups.csv)。',
        '承認根拠はcommit `e50c0002`、確認時刻 `2026-10-23T18:02:20Z`（ユーザーによるClaude確認済みの申告）。[receipt.json](stage2/receipt.json)に記録。凍結`60db4b6`、src hash一致。生ログ・終点は`/tmp/q40a-execution/`に外部保存。',
        '未測定の開発303問には外挿しない。数値的な不達を実数解の不存在とは解釈しない。',
    ]
    (HERE.parent/'answer.md').write_text('\n\n'.join(rows[:7])+'\n\n'+'\n'.join(rows[8:])+'\n')
    print(json.dumps({k:summary[k] for k in ('planned_trials','actual_local_calls','P1','P2','P3','P4','feasibility')}))


if __name__=='__main__':
    analyze()
