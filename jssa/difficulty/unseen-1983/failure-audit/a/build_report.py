"""Build the Q29a result tables ONLY when all five 900s-limit outputs exist."""
from common import *
import csv
import datetime
from benchmarks import research_runner as rr
from geosolver.exact import describe_exact

def public_score(cid, data):
    result = data['solver_result']
    expected = sorted({rr._canonical_json(describe_exact(v).canonical_key())
                       for v in rr.reference_expressions(str(EXPECTED[cid]))})
    actual = rr._answer_keys(result)
    return result['status'] in ('solved','no_answer_found') and actual==expected, actual

def load(path):
    return json.loads(path.read_text())

def table(path, rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def main():
    initial=load(HERE/'experiment-plan.json')['identity']
    final=identity()
    assert initial['src_hash']==final['src_hash']
    assert initial['input_sha256']==final['input_sha256']
    assert initial['assessment_sha256']==final['assessment_sha256']
    old=[json.loads(l) for l in (CORPUS/'prereg/q19-scored/assessment.jsonl').read_text().splitlines()]
    scored=[r for r in old if r['in_target']]
    assert len(scored)==130 and sum(r['matched'] for r in scored)==85
    structures=load(HERE/'structure-summary.json')
    features={r['id']:r for r in structures['Q29a']}
    reasons={
        IDS[0]:'必要なp>=33が初期上限20（NOMAD拡張25）の外。a,bの整数桁・hの有理性は本質的条件。',
        IDS[1]:'既約分母n=32が初期上限20（拡張25）の外。角度条件と整数・Bézout証人を同時探索。',
        IDS[2]:'既約分子m=672、Bézout係数vの絶対値269以上が初期探索範囲の外。',
        IDS[3]:'正解は初期探索範囲内。8変数・24本の明示的凸性不等式。失敗の細分類（局所極小/枝/選択）は未確定。',
        IDS[4]:'表現用整数b=605が初期上限44（拡張55）の外。3変数なので次元だけでは説明できない。'}
    rows, runs, display=[] ,[],[]
    for cid in IDS:
        seed=205 if cid==IDS[3] else 201
        original=[r for r in old if r['case_id']==cid]
        chosen=next(r for r in original if r['seed']==seed)
        assert len(original)==5 and not chosen['matched']
        witness_data=load(HERE/'witnesses'/f'{cid}.json')
        assert all(c['satisfied'] for c in witness_data['conditions'])
        local=[load(HERE/'local'/f'{cid}-sign-{sign}.json') for sign in (1,-1)]
        local_correct=[r['completion']['answer_values']==[str(EXPECTED[cid])] for r in local]
        assert all(local_correct)
        completion=load(HERE/'warm-full'/f'{cid}.json')
        full=load(HERE/'warm-initial'/f'{cid}.json')
        global_run=load(HERE/'global-900'/f'{cid}-seed-{seed}.json')
        completion_ok,_=public_score(cid,completion)
        full_ok,_=public_score(cid,full)
        global_ok,keys=public_score(cid,global_run)
        assert completion_ok
        g=global_run['solver_result']; w=full['solver_result']; f=features[cid]
        assert g['requested_resources']['time_limit_seconds']==900
        assert g['requested_resources']['seed']==seed and g['requested_resources']['cores']==1
        err=w.get('error') or {}
        row=dict(id=cid, conclusion='探索の失敗', dsl_inconsistency_explains_failure=False,
            witness_exists=True, frozen_180_correct=sum(r['matched'] for r in original),frozen_180_runs=5,
            variables=f['variables'],equalities=f['equalities'],inequalities=f['inequalities'],integer_calls=f['integer_calls'],
            max_raw_equality_residual=witness_data['raw_max_abs_equality_residual'],
            min_raw_inequality_margin=witness_data['min_raw_inequality_margin'],
            compiled_guard_ok=witness_data['compiled_guard_ok'],
            compiled_hard_feasible=witness_data['compiled_hard_feasibility']['hard_feasible'],
            expected=EXPECTED[cid], outside_initial_box=json.dumps(witness_data['witness_outside_heuristic_bounds'],ensure_ascii=False),
            local_BC_plus_correct=local_correct[0],local_BC_minus_correct=local_correct[1],
            local_BC_plus_seconds=local[0]['elapsed_seconds'],local_BC_minus_seconds=local[1]['elapsed_seconds'],
            discovery_replaced_full_correct=completion_ok,discovery_replaced_full_seconds=completion['solver_result']['elapsed_seconds'],
            initial_probe_only_full_correct=full_ok,initial_probe_only_full_status=w['status'],
            initial_probe_only_full_seconds=w['elapsed_seconds'],initial_probe_only_full_error=err.get('message',''),
            global_900_seed=seed,comparison_180_status=chosen['status'],comparison_180_seconds=chosen['elapsed'],
            global_900_correct=global_ok,global_900_status=g['status'],global_900_seconds=g['elapsed_seconds'],
            global_900_termination=g['termination_reason'],global_900_answer_keys=json.dumps(keys),
            global_900_numeric_feasible=(g.get('diagnostics') or {}).get('numeric_feasible'),
            mechanism=reasons[cid],development_n_ge_variables=f['development_count_greater_or_equal']['variables'],
            dsl_sha256=witness_data['dsl_sha256'],solver_commit=FROZEN,
            corrected_DSL_run=False,scope='事後診断。凍結版85/130に混ぜない。')
        rows.append(row)
        verdict='正答' if global_ok else ('答えなし' if g['status']=='no_answer_found' else g['status'])
        display.append(f"| {cid} | 探索の失敗 | {row['frozen_180_correct']}/5 | {verdict}・{g['elapsed_seconds']:.1f}秒 | {reasons[cid]} |")
        for r in original:
            runs.append(dict(id=cid,experiment='frozen_180_assessment_only',seed_or_sign=r['seed'],budget_seconds=180,
                elapsed_seconds=r['elapsed'],correct=r['matched'],status=r['status'],
                termination=r['termination'],evidence='../../prereg/q19-scored/assessment.jsonl'))
        for j,r in enumerate(local):
            sign=(1,-1)[j]
            runs.append(dict(id=cid,experiment='posthoc_local_B_C',seed_or_sign=sign,budget_seconds=180,
                elapsed_seconds=r['elapsed_seconds'],correct=local_correct[j],status='verified_exact_answer',
                termination='',evidence=f'local/{cid}-sign-{sign}.json'))
        for group,data,label,s in [('warm-full',completion,'posthoc_discovery_replaced_full',2901),
                                  ('warm-initial',full,'posthoc_initial_probe_only_full',2901),
                                  ('global-900',global_run,'posthoc_original_DSL_900s',seed)]:
            r=data['solver_result']; ok,_=public_score(cid,data)
            fn=f'{cid}-seed-{seed}.json' if group=='global-900' else f'{cid}.json'
            runs.append(dict(id=cid,experiment=label,seed_or_sign=s,budget_seconds=900 if group=='global-900' else 180,
                elapsed_seconds=r['elapsed_seconds'],correct=ok,status=r['status'],
                termination=r['termination_reason'],evidence=f'{group}/{fn}'))
    table(HERE/'results.csv',rows)
    table(HERE/'runs.csv',runs)
    assert len(runs)==50
    report='''直感に反するか：弱い。深い理論が必要か：不要。再現性と広がり：5問で確認、外的再現・広い一般化は未確認。solver固有か：本実装への依存が強い（探索範囲と入力表現）。
**Aの中心を担えるか：不可。成績低下の説明として必要だが、深い新現象ではない。**

5問すべてに元DSLを満たす正しい配置が存在した。今回の失敗原因は **DSLの不整合0問／探索の失敗5問**。凍結版の **85/130は変更しない**。DSL修正版は実行しておらず、以下の延長・近傍試験はすべて別の事後診断である。

| 問題 | 分類 | 元180秒 | 900秒上限・同じ失敗seed | 根拠・残る限界 |
|---|---|---:|---|---|
'''+ '\n'.join(display)+'''

900秒試験は各問1 seed（201、1991-14のみ205）。元の180秒実行からの継続ではない。上限前に探索を終える場合もあり、時間延長だけでは探索範囲を直せない。初期箱に解がない4問でも、高精度refiner・整数補完の別経路まで数学的に不可能とは断定しない。

手計算の配置を100桁で代入し、**全93条件、追加hard check、guardを全問通過**。元等式の最大絶対残差は9.15×10⁻¹⁰⁰未満、不等式はすべて正の余裕を持つ。目標値は順に65、49、677、384、616。[導出と座標](derivations.md)、[全条件の数値](conditions.csv)を保存した。

全変数（整数証人も含む）を絶対値0.01だけ逆方向にずらした2出発点から、凍結refiner＋最終検証は **10/10正答、0.74〜20.52秒**。候補発見だけをこの近傍点に置き換えた完成workerも5/5正答だった。ただし通常の大域探索・範囲を残し、初期probeだけを置き換えると、1991-14は正答（8.29秒）、範囲外の4問はworker終了コード−11となった。**「元の完成solverが近傍から全問解ける」とは言わない**。この異常終了はoracle初期点を渡す診断であり、元130実行の失敗型とは別。

開発323問は変数中央値3・最大9、IsInteger使用3問。今回は10変数が1問、8変数が2問、IsInteger使用4問。1991-14の明示的不等式24本は開発群の関係式としての不等式最大12本より多いが、開発群にはConvexPolygon等のpredicateもあるため、これは記法の比較であって内在的難度の比較ではない。[全323問との比較](structure.csv)。開発中の修正履歴からの因果判定はQ29aの範囲外。

**1983-12は特に注意：a,bの整数桁とhの有理性は出力形式ではなく原文の条件。単純に整数変数を除く書換えは同値でない。** 他3問のm+n／a+b用整数証人とは区別する。

詳細表は [results.csv](results.csv)、実行を種類別に区別した表は [runs.csv](runs.csv)。srcは60db4b6と一致し、元DSL・assessmentのhashも前後一致。封印tar・封印生データは未参照。1991-14の900秒試験と通常探索を残す近傍試験は、初回に保存前のサイズ制限で結果を残せず、それぞれ一度再実行した。保存失敗分の正誤は不明で、成功率推定には使えない（[記録](operational-events.json)）。全ファイル5MB未満、同時solver最大4、各1コア。
'''
    (HERE/'answer.md').write_text(report)
    summary=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), identity=final,
        original_score=dict(correct=85,runs=130,unchanged=True), original_selected=dict(correct=4,runs=25),
        witness_count=5,condition_count=93,classification=dict(DSL_error=0,search_failure=5),
        posthoc_900_correct=sum(r['global_900_correct'] for r in rows),posthoc_900_n=5,
        near_local_BC_correct=10,near_local_BC_n=10,discovery_replaced_full_correct=5,
        initial_probe_only_full_correct=sum(r['initial_probe_only_full_correct'] for r in rows),
        initial_probe_only_full_engine_errors=sum(r['initial_probe_only_full_status']=='engine_error' for r in rows),
        corrected_DSL_runs=0,full_raw_seal_accessed=False,maximum_parallel_solver_streams=4,
        file_size_limit_bytes=4_900_000)
    save(HERE/'summary.json',summary)
    files={str(p.relative_to(HERE)):dict(bytes=p.stat().st_size,sha256=sha(p))
           for p in HERE.rglob('*') if p.is_file() and p.name!='artifact-manifest.json'}
    assert all(v['bytes']<5_000_000 for v in files.values())
    save(HERE/'artifact-manifest.json',dict(files=files,max_file_bytes=max(v['bytes'] for v in files.values()),
        total_bytes=sum(v['bytes'] for v in files.values()),note='Per-file limit, not aggregate limit.'))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
