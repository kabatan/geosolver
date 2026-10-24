"""Problem-paired preregistered analysis. No benchmark or solver calls."""
from __future__ import annotations
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from stage2_common import *


def readlines(p):
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def csv_file(name,rows):
    with (OUT/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    assert_identity()
    audit=json.loads((OUT/'execution/lowering-audit.json').read_text())
    selected=json.loads((OUT/'selection.json').read_text());N=len(selected)
    local_jobs=json.loads((RAW/'local-jobs.json').read_text())
    full_jobs=json.loads((RAW/'full-jobs.json').read_text())
    jjobs=json.loads((RAW/'jacobian-jobs.json').read_text())
    assert all((RAW/'local'/f'{i:04d}'/'done.json').exists() for i in range(len(local_jobs)))
    assert all((RAW/'full'/f'{i:04d}'/'verification.json').exists() for i in range(len(full_jobs)))
    assert all((RAW/'jacobian'/f'{i:04d}'/'done.json').exists() for i in range(len(jjobs)))
    local={};reasons=Counter();duplicate=[]
    for f in sorted((RAW/'local').glob('*/records.jsonl')):
        for r in readlines(f):
            key=(r['id'],r['arm'],r['k'])
            if key in local:duplicate.append(key)
            local[key]=r;reasons[r['reason']]+=1
    assert not duplicate,duplicate
    full={(r['id'],r['arm'],r['seed']):json.loads((RAW/'full'/f'{i:04d}'/'verification.json').read_text()) for i,r in enumerate(full_jobs)}
    jdata=defaultdict(list)
    for i in range(len(jjobs)):
        raw_record=RAW/'jacobian'/f'{i:04d}'/'done.json'
        r=json.loads(raw_record.read_text());r['_raw_record']=str(raw_record);jdata[r['id'],r['arm']].append(r)
    arm_rows=[];seed_rows=[];arm_values={};jacobian_rows=[]
    for p in audit:
        cid=p['id']
        for arm in ARMS:
            meta=p['arms'][arm];rows=[local[cid,arm,k] for k in range(200) if (cid,arm,k) in local]
            wins=sum(bool(r['success']) for r in rows);half=[sum(r['success'] for r in rows if 100*h<=r['k']<100*(h+1))/100 for h in range(2)]
            values=[]
            for seed in SEEDS:
                q=full.get((cid,arm,seed));T=q['T'] if q else 180
                seed_rows.append(dict(id=cid,family=p['family'],arm=arm,seed=seed,T=T,
                     censored=q['censored'] if q else True,reason=q['reason'] if q else meta['status'],
                     candidate_count=q.get('candidate_count',0) if q else 0,
                     verified_count=q.get('verified_count',0) if q else 0,
                     observation_complete=q.get('observation_complete',False) if q else False))
                values.append(T)
            jgood=[r for r in jdata[cid,arm] if r['status']=='measured']
            representative={}
            for step in ('1e-5','1e-6','1e-7'):
                representative[step]={}
                for version in ('raw','normalized'):
                    for field in ('sigma_min','sigma_max'):
                        nums=[float(r['steps'][step][version][field]) for r in jgood]
                        representative[step][version+'_'+field]=float(np.median(nums)) if nums else None
            for r in jdata[cid,arm]:
                for step in ('1e-5','1e-6','1e-7'):
                    for version in ('raw','normalized'):
                        z=r.get('steps',{}).get(step,{}).get(version,{})
                        jacobian_rows.append(dict(id=cid,arm=arm,k=r['k'],status=r['status'],reason=r.get('reason'),
                            h=step,version=version,m=r.get('m'),n=r.get('n'),rank=z.get('rank'),
                            sigma_min=z.get('sigma_min'),sigma_max=z.get('sigma_max'),ratio=z.get('ratio'),
                            raw_record=r['_raw_record'],
                            displacement=r.get('displacement_normalized'),branch_change_suspected=r.get('branch_change_suspected'),
                            effective=r.get('efficacy',{}).get('effective')))
            v=dict(p=wins/200,wins=wins,half=half,half_wins=[sum(r['success'] for r in rows if 100*h<=r['k']<100*(h+1)) for h in range(2)],T=values,J=representative,J_good=len(jgood),
                   status=meta['status'],method=meta.get('method'),observations=len(rows))
            arm_values[cid,arm]=v
            arm_rows.append(dict(id=cid,family=p['family'],arm=arm,status=meta['status'],
                 p_measured=v['p'] if meta['status']=='ready' else None,p_dagger=v['p'],
                 attempted=len(rows),successes=wins,denominator=200,p_first100=half[0],p_last100=half[1],
                 method=v['method'],T_mean=float(np.mean(values)),T_seed1=values[0],T_seed2=values[1],T_seed3=values[2],
                 J_selected=len(jdata[cid,arm]),J_measured=len(jgood),
                 sigma_min_raw=representative['1e-6']['raw_sigma_min'],sigma_min_normalized=representative['1e-6']['normalized_sigma_min']))
    reviewed=json.loads((OUT/'mechanism-reviewed.json').read_text()) if (OUT/'mechanism-reviewed.json').exists() else {}
    problems=[]
    for p in audit:
        cid=p['id'];o=arm_values[cid,'original'];a=arm_values[cid,'break_p01'];b=arm_values[cid,'break_m01']
        delta=(a['wins']+b['wins']-2*o['wins'])/400;R=float(np.mean((np.array(a['T'])+b['T'])/2)/max(.001,np.mean(o['T'])))
        ten=True;deg=True;j_available=True
        for h in ('1e-5','1e-6','1e-7'):
            jo=o['J'][h];ja=a['J'][h];jb=b['J'][h]
            lo,hi=jo['normalized_sigma_min'],jo['normalized_sigma_max']
            usable=all(z['normalized_sigma_min'] is not None and z['normalized_sigma_max'] is not None and z['normalized_sigma_max']>0 for z in (jo,ja,jb))
            j_available=j_available and usable
            ten=ten and usable and ja['normalized_sigma_min']>=10*max(1e-12,lo) and jb['normalized_sigma_min']>=10*max(1e-12,lo)
            deg=deg and lo is not None and hi is not None and hi>0 and lo/hi<=1e-8
        # The registration explicitly excludes unclassified structural zeros.
        # Numerical rank/conditioning alone never establishes branch merger.
        annotation=reviewed.get(cid,{})
        mechanism=bool(ten and annotation.get('structural_ambiguity_resolved',False) and annotation.get('intervention_effective',False))
        deg_supported=bool(deg and annotation.get('degeneracy_eligible',False))
        problems.append(dict(id=cid,family=p['family'],applicable=all(p['arms'][x]['status']=='ready' for x in ARMS),
            method=o['method'],p_original=o['p'],p_break_plus=a['p'],p_break_minus=b['p'],delta_p=delta,R_T=R,
            delta_first100=(a['half_wins'][0]+b['half_wins'][0]-2*o['half_wins'][0])/200,
            delta_last100=(a['half_wins'][1]+b['half_wins'][1]-2*o['half_wins'][1])/200,
            J_comparison_available=j_available,J_both_signs_10x=bool(ten),O_numerically_degenerate=bool(deg),
            mechanism_support=mechanism,degeneracy_support=deg_supported,
            joint_numeric=bool(delta>=.05 and R<=.8 and ten),joint_support=bool(delta>=.05 and R<=.8 and mechanism),
            mechanism_reason=annotation.get('reason','structural cause / branch merger not established')))
    delta_num=np.array([round(r['delta_p']*400) for r in problems],dtype=np.int64)
    delta=delta_num/400;mean_delta=float(delta_num.sum()/(400*N));logR=np.log([r['R_T'] for r in problems])
    idx=np.random.default_rng(410291).integers(0,N,size=(10000,N))
    ci=lambda values:[float(x) for x in np.percentile(np.mean(np.asarray(values)[idx],axis=1),[2.5,97.5])]
    dp_ci=[float(x) for x in np.percentile(np.sum(delta_num[idx],axis=1)/(400*N),[2.5,97.5])]
    lr_ci=ci(logR);pos=int(sum(delta_num>0));fast=sum(r['R_T']<=.8 for r in problems)
    p1=bool(delta_num.sum()>=20*N and pos>=math.ceil(.5*N) and dp_ci[0]>0)
    p2=bool(fast>=math.ceil(.5*N) and logR.mean()<0 and lr_ci[1]<0)
    c10=sum(r['mechanism_support'] for r in problems);cd=sum(r['degeneracy_support'] for r in problems)
    p3=c10>=math.ceil(.5*N) and cd>=math.ceil(.25*N)
    cj=sum(r['joint_support'] for r in problems);p4=cj>=math.ceil(.25*N)
    prediction={'N':N,'P1':{'mean_delta':mean_delta,'positive_problems':pos,'ci95':dp_ci,'conditions_met':p1,'supported':p1},
        'P2':{'fast_problems':fast,'mean_log_ratio':float(logR.mean()),'ci95':lr_ci,'conditions_met':p2,'supported':p1 and p2},
        'P3':{'tenfold_eligible':c10,'degenerate_eligible':cd,'numeric_tenfold':sum(r['J_both_signs_10x'] for r in problems),
              'numeric_degenerate':sum(r['O_numerically_degenerate'] for r in problems),'available_comparisons':sum(r['J_comparison_available'] for r in problems),'conditions_met':p3,'supported':p1 and p2 and p3},
        'P4':{'joint_eligible':cj,'joint_numeric':sum(r['joint_numeric'] for r in problems),'conditions_met':p4,'supported':p1 and p2 and p3 and p4},
        'reverse_p_evidence':dp_ci[1]<=0,'reverse_time_evidence':lr_ci[0]>=0,
        'bootstrap':{'unit':'problem (all arms/seeds together)','seed':410291,'repetitions':10000,'method':'percentile95'}}
    generated=[r['id'] for r in selected if r['arms']['sham']['status']=='syntax_checked']
    sham_p=[abs(arm_values[c,'sham']['wins']-arm_values[c,'original']['wins'])/200 for c in generated
            if all(arm_values[c,a]['observations']==200 for a in ('original','sham'))]
    sham_num=sum(round(v*200) for v in sham_p)
    sham_mean=sham_num/(200*len(sham_p)) if sham_p else float('nan')
    sham_logs=[math.log(max(.001,arm_values[c,'sham']['T'][s])/max(.001,arm_values[c,'original']['T'][s]))
               for c in generated for s,seed in enumerate(SEEDS)
               if all(full.get((c,a,seed),{}).get('observation_complete',False) for a in ('original','sham'))]
    w_num=sum(arm_values[c,'row_scale']['wins']-arm_values[c,'original']['wins'] for c in generated)
    b_num=sum(arm_values[c,'break_p01']['wins']+arm_values[c,'break_m01']['wins']-2*arm_values[c,'original']['wins'] for c in generated)
    w_mean=w_num/(200*len(generated));b_mean=b_num/(400*len(generated))
    sham_gm=float(np.exp(np.mean(sham_logs))) if sham_logs else float('nan')
    controls={'generated_problems':len(generated),'sham_mean_absolute_delta_p':sham_mean,
       'sham_time_geometric_ratio_all_seed_pairs':sham_gm,'sham_failed':bool(sham_num>4*len(sham_p) or not .9<=sham_gm<=1.1 or len(sham_logs)!=3*len(generated) or len(sham_p)!=len(generated)),
       'weight_mean_delta_p':w_mean,'break_mean_delta_p_same_problems':b_mean,
       'weight_reproduces_80pct':bool(5*w_num>=2*b_num) if b_num>0 else None,
       'unmeasured_sham_slots':sum(200-arm_values[c,'sham']['observations'] for c in generated),
       'unmeasured_sham_time_pairs':3*len(generated)-len(sham_logs)}
    by_family={}
    for family in sorted({r['family'] for r in problems}):
        rows=[r for r in problems if r['family']==family]
        by_family[family]={'N':len(rows),'applicable':sum(r['applicable'] for r in rows),
             'mean_delta_p':sum(round(r['delta_p']*400) for r in rows)/(400*len(rows)),
             'mean_log_R':float(np.mean([math.log(r['R_T']) for r in rows])),
             'positive_problems':sum(r['delta_p']>0 for r in rows)}
    seed_logs=[float(np.mean([math.log(max(.001,(arm_values[r['id'],'break_p01']['T'][s]+arm_values[r['id'],'break_m01']['T'][s])/2)/max(.001,arm_values[r['id'],'original']['T'][s])) for r in problems])) for s in range(3)]
    halves=[sum(round(r[key]*200) for r in problems)/(200*N) for key in ('delta_first100','delta_last100')]
    secondary={'by_family':by_family,'half_mean_delta_p':halves,'seed_mean_log_R':dict(zip(map(str,SEEDS),seed_logs)),
               'halves_stable':all(v>0 for v in halves),'time_seeds_stable':all(v<0 for v in seed_logs),'comparisons':{}}
    for group,ids in [('all',[r['id'] for r in problems]),('applicable',generated),
                      ('LM',[r['id'] for r in problems if r['method']=='LM']),('Powell',[r['id'] for r in problems if r['method']=='Powell'])]:
        for arm in ('break_p01','break_m01','break_p001','break_m001','sham','row_scale'):
            secondary['comparisons'][group+':'+arm]={'N':len(ids),
                'mean_delta_p':float(np.mean([(arm_values[c,arm]['wins']-arm_values[c,'original']['wins'])/200 for c in ids])) if ids else None,
                'mean_log_R':float(np.mean([math.log(max(.001,np.mean(arm_values[c,arm]['T']))/max(.001,np.mean(arm_values[c,'original']['T']))) for c in ids])) if ids else None}
    expected=sum(map(len,local_jobs));incomplete=sum(1 for r in local.values() if r['reason']=='interrupted_no_retry')+expected-len(local)
    observation_missing=sum(not r.get('observation_complete',False) for r in full.values())
    run_audit={'local_planned':56000,'local_executable':expected,'local_completed_records':len(local),
        'local_successes':sum(r['success'] for r in local.values()),'local_reason_counts':dict(reasons),
        'local_incomplete':incomplete,'full_planned':840,'full_executable':len(full_jobs),'full_verified':len(full),
        'local_incomplete_rate':incomplete/expected,'full_observation_missing_rate':observation_missing/len(full_jobs),
        'full_reason_counts':dict(Counter(r['reason'] for r in full.values())),
        'full_observation_missing':observation_missing,'static_inapplicable_problems':N-len(generated),
        'executable_incomplete_rate':(incomplete+observation_missing)/(expected+len(full_jobs)),
        'jacobian_selected':len(jjobs),'jacobian_measured':sum(r['status']=='measured' for rs in jdata.values() for r in rs),
        'jacobian_reason_counts':dict(Counter(r.get('reason') or 'measured' for rs in jdata.values() for r in rs)),
        'original_source_hash':assert_identity(),'finished_utc':utc()}
    batches=readlines(OUT/'execution/batches.jsonl');loads=[r['load'][0] for r in batches]
    run_audit['load1_range']=[min(loads),max(loads)] if loads else None
    broad=N>=20 and len(by_family)>=2 and all(v['applicable']>=3 and v['mean_delta_p']>0 and v['mean_log_R']<0 and v['positive_problems']>=math.ceil(v['N']/2) for v in by_family.values())
    claim=bool(p1 and p2 and p3 and p4 and broad and secondary['halves_stable'] and secondary['time_seeds_stable'] and not controls['sham_failed'] and controls['weight_reproduces_80pct'] is not True and run_audit['executable_incomplete_rate']<=.05)
    save(OUT/'predictions.json',prediction);save(OUT/'controls.json',controls);save(OUT/'secondary.json',secondary);save(OUT/'analysis-checks.json',run_audit)
    csv_file('per-problem.csv',problems);csv_file('per-arm.csv',arm_rows);csv_file('per-seed.csv',seed_rows)
    if jacobian_rows:csv_file('jacobians.csv',jacobian_rows)
    result='登録した改善を支持した' if claim else '登録した広い改善・機構の予言を支持できない。Aの中心として不可'
    state=lambda key:'支持' if prediction[key]['supported'] else '不支持（主検定未通過）' if key!='P1' and not p1 else '不支持'
    text=f'''# Q41：{result}

| 冒頭判定 | 結論 |
|---|---|
| ①直感に反するか | 対称性を破ると広く容易になる、という登録した逆転は{'支持' if claim else '未再現'}。 |
| ②深い理論が必要か | 必要性を示せない。同変分岐の群作用・枝の合流は未証明。条件数の変化だけで説明できるかも未確定。 |
| ③広く再現するか | 開発323問から固定した40問。生成可能23問、p改善{pos}/40問、20%以上の時間改善{fast}/40問。未使用群の再現ではない。 |
| ④solverならではか | 示せない。他の数値最適化法との比較はしていない。 |
| 人間が導けるか | 対称性だけでは特異点を保証しない、という反例は紙で作れる。今回の効果量は計測が必要。 |
| 他手法でも得られるか | 可能性があるが未測定。 |
| Aの中心を担えるか | {'要検討' if claim else '不可'}。 |

| 予言 | 全40問での結果 | 判定 |
|---|---|---|
| P1：平均Δp≥0.05、改善≥20問、区間下端>0 | 平均{mean_delta:+.4f}、改善{pos}/40、95%区間[{dp_ci[0]:+.4f}, {dp_ci[1]:+.4f}] | {state('P1')} |
| P2：時間比≤0.8が≥20問、平均log比の区間上端<0 | {fast}/40、平均log比{logR.mean():+.3f}、95%区間[{lr_ci[0]:+.3f}, {lr_ci[1]:+.3f}] | {state('P2')} |
| P3：両符号10倍≥20問、原版退化≥10問 | 数値上はそれぞれ{prediction['P3']['numeric_tenfold']}/40、{prediction['P3']['numeric_degenerate']}/40。機構支持として数えられるのは{c10}/40、{cd}/40。 | {state('P3')} |
| P4：同じ問でp・時間・Jが改善≥10問 | 数値条件{prediction['P4']['joint_numeric']}/40、機構支持{cj}/40 | {state('P4')} |

pは各条件200始点からの条件適合図への到達率、Tは同基準を通る候補の最初の発生時刻。Δpは±1%の平均から元版を引いた値。変換不能17問も失敗として分母に残すので、主解析は介入手順全体の成績であり、対称性そのものの効果とは分けて読む。区間は問題単位10,000回の固定bootstrap。反対向きの登録基準にpは{'該当' if prediction['reverse_p_evidence'] else '非該当'}、時間は{'該当' if prediction['reverse_time_evidence'] else '非該当'}。未発見を解不存在とは呼ばず、対称性が無関係だとも結論しない。

無変更の書換えSは平均|Δp|={controls['sham_mean_absolute_delta_p']:.4f}、時間比の幾何平均={sham_gm:.3f}で、登録した対照診断は{'不合格' if controls['sham_failed'] else '通過'}。同じ23問でWの平均Δp={w_mean:+.4f}、B={b_mean:+.4f}。始点前半／後半の平均Δpは{halves[0]:+.4f}／{halves[1]:+.4f}、時間の3seed別平均log比は{' / '.join(f'{v:+.3f}' for v in seed_logs)}。{'両半分・全seedで同方向という要件も満たさない。' if not (secondary['halves_stable'] and secondary['time_seeds_stable']) else '両半分・全seedで方向は揃った。'} 族別・±0.1%・符号別・LM/Powell別は [secondary.json](secondary.json)。

Jは局所成功の番号順で最大5点だけを別途精密化した。{run_audit['jacobian_measured']}/{len(jjobs)}点を測定。小さい特異値が連続自由度だけに由来するか、枝の合流かを判別できない例は、登録どおり機構支持0。精密化の成功をpに加えていない。

前回はcommit `795565c2` のpush確認（UTC 2026-10-23T17:43:24Z）後、最初の実行前に中断。生存プロセス・既存試行とも0で、失われた試行の置換や追加seedはない。`/tmp/q41-clean` の `60db4b6`、固定hash、指定依存版を照合して再開した。局所{len(local)}/{expected}枠、完成{len(full)}/{len(full_jobs)}枠の記録が揃い、観測欠測{observation_missing}枠。最大2並列。共有32コアのload1は{min(loads):.1f}〜{max(loads):.1f}で、時間Tに加え2秒上限のpも負荷の影響を受ける。候補保存費用はTに含む。完成solverは各版の通常の探索箱・残差尺度を使うため、Tにはそれらの違いも含まれる。

全40問の主表は [per-problem.csv](per-problem.csv)、失敗内訳は [analysis-checks.json](analysis-checks.json)、許可・環境は [execution/receipt.json](execution/receipt.json)。5MB超を含む生ログ・全始点・終点・候補は `/tmp/q41-stage2/` に外部保存し、[raw-manifest.json](raw-manifest.json) にhashを残した。
'''
    (OUT/'answer.md').write_text(text)
    print(json.dumps({'claim_supported':claim,'P1':prediction['P1'],'P2':prediction['P2'],'audit':run_audit},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
