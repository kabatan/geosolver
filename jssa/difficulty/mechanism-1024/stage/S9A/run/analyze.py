"""Fixed A1/A2/A3 judgments from saved outputs; never invokes solver code."""
import csv,hashlib,json
from decimal import Decimal,localcontext
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text());ROOT=Path(M['scratch'])
ARMS=['R0','R1','R2','R3']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text()) if p.exists() else None
def num(x):
    if x is None or x=='':return None
    try:
        v=Decimal(str(x));return None if v.is_nan() else v
    except Exception:return None
def short(x):
    v=num(x)
    return '' if v is None else format(v,'.18E')
def write(p,v):
    data=json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n';assert len(data.encode())<3_000_000;p.write_text(data)
def csvout(p,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    assert p.stat().st_size<3_000_000

def main():
    problems=[];candidates=[]
    for t in M['inputs']:
        case=t['case_id'];d=ROOT/'runs'/case;cl=t['classification'];im=read(d/'initial-metrics.json');missing=read(d/'missing.json')
        ini=read(d/'initial.json')
        count=im['count'] if im else len(ini.get('candidates',[])) if ini else 0
        sigma=cl['sigma_base'];sj=cl['base_judgment'] if cl['base_judgment'] in ['特異','非特異'] else '欠測'
        r=dict(case_id=case,seed=0,in_s1=t['in_s1'],in_72=t['in_72'],n_variables=t['n_variables'],initial_candidates=count,candidate_available=count>0,initial_origin=t['reuse']['origin'] if t['reuse'] else 'new_seed0_primary_search',initial_sha256=sha(d/'initial.pkl') if (d/'initial.pkl').exists() else '',sigma_base=sigma,sigma_group=sj,sigma_status=cl['status'],sigma_reason=cl['reason'],initial_residual_median=im.get('median_residual') or '' if im else '',missing_reason=missing['reason'] if missing else '')
        for arm in ARMS:
            ref=read(d/(arm+'.refinement.json'));meas=read(d/(arm+'.measure.json'));ver=read(d/(arm+'.verification.json'))
            end=read(d/('refine.'+arm+'.ended.json'))
            good_ref=ref is not None and end is not None and end['returncode']==0 and end['reason'] is None
            rows=meas['rows'] if meas else []
            available=[q for q in rows if num(q.get('error_digits_exact')) is not None]
            best=max(available,key=lambda q:num(q['error_digits_exact'])) if available else None
            # Incomplete measurement cannot establish the best of the entire returned tuple.
            complete=bool(meas and meas['complete'] and good_ref)
            r.update({arm+'_digits':short(best['error_digits_exact']) if best and complete else '',arm+'_digits_exact':best['error_digits_exact'] if best and complete else '',arm+'_best_uid':best['candidate_uid'] if best and complete else '',arm+'_converged':ref['converged'] if good_ref else '',arm+'_hard_feasible':ref['hard_feasible'] if good_ref else '',arm+'_seconds':ref['seconds'] if good_ref else '',arm+'_attempted':ref['attempted'] if good_ref else '',arm+'_returned':ref['returned'] if good_ref else '',arm+'_unattempted':ref['unattempted'] if good_ref else '',arm+'_immediate_pass':sum(q['immediate_pass'] for q in rows) if complete else '',arm+'_final_pass':sum(q['final_pass'] for q in ver['rows']) if ver else '',arm+'_verification_complete':bool(ver and ver['complete']),arm+'_measurement_complete':complete,arm+'_missing_reason':'' if best and complete else 'no_candidates' if not count else 'refinement_unavailable' if not good_ref else 'measurement_incomplete' if not complete else 'no_finite_target_value'})
            verify_by_uid={q['candidate_uid']:q for q in ver['rows']} if ver else {}
            times=ref.get('candidate_seconds',{}) if ref else {}
            for q in rows:
                v=verify_by_uid.get(q['candidate_uid'],{})
                candidates.append(dict(case_id=case,seed=0,arm=arm,rank=q['rank'],candidate_id=q['candidate_id'],candidate_uid=q['candidate_uid'],source_uid=q['source_uid'],status=q['status'],hard_feasible=q['hard_feasible'],immediate_pass=q['immediate_pass'],digits=short(q.get('error_digits_exact')),absolute_error=short(q.get('absolute_error')),solver_residual=short(q.get('solver_residual')),coordinate_dps=q['coordinate_dps'],candidate_seconds=times.get(q['source_uid'],times.get(q['candidate_uid'],'')),final_pass=v.get('final_pass',''),final_status=v.get('status','missing'),answer_error=q.get('answer_error','')))
        problems.append(r)
    population=[r for r in problems if r['n_variables']>0]
    eligible=[r for r in population if r['candidate_available']]
    medians=sorted(num(r['initial_residual_median']) for r in eligible if num(r['initial_residual_median']) is not None)
    with localcontext() as ctx:
        ctx.prec=750
        median=(medians[len(medians)//2] if len(medians)%2 else (medians[len(medians)//2-1]+medians[len(medians)//2])/2) if medians else None
    for r in problems:r['large_initial_residual']=bool(median is not None and num(r['initial_residual_median']) is not None and num(r['initial_residual_median'])>median)
    def comparison(r,arm,kind):
        a=num(r['R0_digits_exact']);b=num(r[arm+'_digits_exact'])
        if kind=='count':
            a=num(r['R0_converged']);b=num(r[arm+'_converged'])
        if a is None or b is None:return None
        return b<a if kind=='count' else a-b>=40 if kind=='loss40' else abs(a-b)<=20
    def judge(rows,arm,kind,threshold):
        values=[comparison(r,arm,kind) for r in rows];n=len(rows);k=sum(v is True for v in values)
        return dict(numerator=k,denominator=n,comparable=sum(v is not None for v in values),missing=sum(v is None for v in values),rate=k/n if n else None,threshold=threshold,passed=(Decimal(k)>=Decimal(str(threshold))*n) if n else None,success_cases=[r['case_id'] for r,v in zip(rows,values) if v is True],missing_cases=[r['case_id'] for r,v in zip(rows,values) if v is None])
    singular=[r for r in eligible if r['sigma_group']=='特異'];regular=[r for r in eligible if r['sigma_group']=='非特異'];large=[r for r in eligible if r['large_initial_residual']]
    a1={f'{group}_{arm}':judge(rows,arm,kind,threshold) for group,rows,kind,threshold in [('singular',singular,'loss40',.5),('nonsingular',regular,'within20',.7)] for arm in ['R1','R3']}
    a1pass=all(v['passed'] for v in a1.values()) if all(v['passed'] is not None for v in a1.values()) else None
    a2=judge(large,'R3','count',.7);a3=judge(eligible,'R2','within20',.8)
    joints={}
    for group,rows,kind,th in [('singular',singular,'loss40',.5),('nonsingular',regular,'within20',.7)]:
        vals=[(comparison(r,'R1',kind),comparison(r,'R3',kind)) for r in rows]
        k=sum(a is True and b is True for a,b in vals)
        joints[group]=dict(numerator=k,denominator=len(rows),rate=k/len(rows) if rows else None,threshold=th)
    judgments=dict(created_utc=datetime.now(timezone.utc).isoformat(),A1=dict(passed=a1pass,conditions=a1,joint_descriptive=joints),A2=a2,A3=a3,
        A3_all_search_variable_problems_conservative=judge(population,'R2','within20',.8),
        population=dict(union=len(problems),search_variables=len(population),zero_variables=len(problems)-len(population),candidates=len(eligible),no_candidates=len(population)-len(eligible),sigma_singular=len(singular),sigma_nonsingular=len(regular),sigma_missing=sum(r['sigma_group']=='欠測' for r in eligible),initial_median_available=len(medians),initial_median_missing=len(eligible)-len(medians),large=len(large)),
        all_problem_initial_residual_median=short(median),denominator_policy='candidate-producing fixed population; comparison missing remains denominator and is not success; sigma-unknown and residual-unknown counts disclosed; all-variable conservative A3 also reported',retries=0)
    csvout(OUT/'per-problem.csv',problems);csvout(OUT/'per-candidate.csv',candidates);write(OUT/'judgments.json',judgments)
    def result(v):return '判定不能' if v is None else '成立' if v else '外れ'
    def frac(v):return f"{v['numerator']}/{v['denominator']} ({100*v['rate']:.1f}%)、比較欠測{v['missing']}" if v['rate'] is not None else '分母0'
    lines=['| 予測 | 判定 | 分子/分母・欠測 |','| --- | --- | --- |',f"| A1 | {result(a1pass)} | "+'；'.join(k+': '+frac(v) for k,v in a1.items())+' |',f"| A2 | {result(a2['passed'])} | {frac(a2)} |",f"| A3 | {result(a3['passed'])} | {frac(a3)} |",'',f"対象和集合{len(problems)}問、探索変数あり{len(population)}問、候補あり{len(eligible)}問。変数0は{len(problems)-len(population)}問、探索変数あり候補欠測は{len(population)-len(eligible)}問。再試行・別seed・対象入替なし。",f"σ_base分類：特異{len(singular)}問、非特異{len(regular)}問、未確定/欠測{judgments['population']['sigma_missing']}問（再計算なし）。A1はR1/R3を各別に判定し4条件全てを要求。両構成同時条件もjudgments.jsonに保存。",f"初期残差の問題別中央値の全問題中央値 = {short(median)}。定義可能{len(medians)}/{len(eligible)}問、strictly greaterのlarge群{len(large)}問。",'比較値の欠測は各群の分母に残し非成功として集計。σ/初期残差が不明な問題は群を割り当てず総数を明示。候補なしも含めた探索変数あり全対象でのA3保守的集計: '+frac(judgments['A3_all_search_variable_problems_conservative'])+'。','',f"生ログ・保存候補・返却座標・詳細測定・開始終了receipt: `{ROOT}`。各ファイル3MB未満。",'1ジョブ1コア・内部1スレッド・最大6並列。精密化90秒は候補集合全体。精密化時間と共有機負荷を保存し、速度を一般化しない。最終検証は凍結版の独立プロセス。桁数は検証前の返却座標に対する絶対誤差（上限600）、負値も保持。収束数はrefinerのconverged_count。','', '| 問題 | σ_base | 分類 | 初期残差中央値 | R0桁 | R1桁 | R2桁 | R3桁 | 収束数R0/R1/R2/R3 |','| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in problems:
        digits=[f"{float(r[a+'_digits']):.3f}" if r[a+'_digits'] else '欠測' for a in ARMS]
        lines.append('| '+' | '.join([r['case_id'],r['sigma_base'] or '欠測',r['sigma_group'],short(r['initial_residual_median']) or '欠測',*digits,'/'.join(str(r[a+'_converged']) if r[a+'_converged']!='' else '欠測' for a in ARMS)])+' |')
    lines+=['','欠測・構造的対象外:']
    lines += [f"- {r['case_id']}: {r['missing_reason']}" for r in problems if r['missing_reason']]
    for r in eligible:
        for arm in ARMS:
            if r[arm+'_missing_reason']:lines.append(f"- {r['case_id']} {arm}: {r[arm+'_missing_reason']}")
    (OUT/'answer.md').write_text('\n'.join(lines)+'\n')
    # Hashes are split by problem to keep every artifact under 3MB.
    hashdir=OUT/'raw-hashes';hashdir.mkdir(exist_ok=True);index={}
    for t in M['inputs']:
        d=ROOT/'runs'/t['case_id'];v={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(d.rglob('*')) if p.is_file()}
        dest=hashdir/(t['case_id']+'.json');write(dest,v);index[str(dest.relative_to(OUT))]=dict(sha256=sha(dest),files=len(v))
    top={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(ROOT.iterdir()) if p.is_file()}
    write(OUT/'raw-hashes.json',dict(scratch=str(ROOT),top=top,per_problem=index))
    with (OUT/'progress.md').open('a') as f:f.write(f"\n{judgments['created_utc']} 集計完了: A1={result(a1pass)}, A2={result(a2['passed'])}, A3={result(a3['passed'])}。監査へ。\n")
    print(json.dumps({'population':judgments['population'],'A1':a1pass,'A2':a2['passed'],'A3':a3['passed']},ensure_ascii=False))
if __name__=='__main__':main()
