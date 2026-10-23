"""Render the final Japanese report from completed, audited measurements."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent
ARMS=("B","N","G2")


def f(x, digits=4):
    return "欠測" if x is None else f"{x:.{digits}f}"


def verdict(x):
    return "判定不能" if x is None else "成立" if x else "不成立"


def delta(x):
    return "欠測" if x is None else f"{100*x:+.2f}ポイント"


def main():
    s=json.loads((HERE/"summary.json").read_text())
    audit=json.loads((HERE/"audit.json").read_text())
    recovery=json.loads((HERE/"recovery-summary.json").read_text())
    checks=json.loads((HERE/"final-checks.json").read_text())
    sensitivity=json.loads((HERE/"recovery-sensitivity.json").read_text())
    completion=json.loads((HERE/"completion-reconciliation.json").read_text())
    assert s["final"]
    start=json.loads((HERE/"execution-freeze.json").read_text())["started_utc"]
    end=json.loads((HERE/"run-complete.json").read_text())["completed_utc"]
    elapsed=(datetime.fromisoformat(end.replace("Z","+00:00"))-datetime.fromisoformat(start.replace("Z","+00:00"))).total_seconds()
    rows=list(csv.DictReader((HERE/"per-problem.csv").open()))
    n=s["problems_expected"]
    p=s["means"]
    d=s["delta_N"]
    v=s["verdicts"]
    c=s["correlations"]
    m=s["mechanism"]
    bad=s["risk"]
    pair=s["paired"]
    counts=s["class_counts_all_observed"]
    q=[]
    add=q.append
    add("# Q1：探索中の許容条件は、どれだけ広く難しさの源か\n")
    add("**Aの中心を担えるか：縮小。** hard罰則を外す平均改善は測れたが、広がりの事前基準に届かず、"
        "φの予測力をこの罰則で説明する予測も外れた。局所探索の機構分析として残す。これは研究上の評価であり、"
        "以下のP1〜P5・M1は事前登録の閾値だけで判定した。\n")
    add("## 結論\n")
    add(f"全{n}問・{s['starts_expected']:,}保存開始点の比較を終了した。hard罰則を探索中だけ外すNの問題平均成功率は "
        f"{p['B']:.4f} → {p['N']:.4f}（{delta(d['mean'])}、問題単位95%区間 "
        f"[{100*d['ci95'][0]:+.2f}, {100*d['ci95'][1]:+.2f}]ポイント）だった。"
        f"事前に固定した「広く改善する」P1は**{verdict(v['P1'])}**。\n")
    add("平均差の区間下端は0より大きい。しかし平均改善3ポイント以上には届かず、"
        f"10ポイント以上改善した問題も{s['delta_counts']['ge_0.10']}問で、固定した30問以上に届かなかった。"
        "改善がないという結果ではなく、予告した大きさ・広がりが出なかったという結果である。\n")
    add(f"φの予測力がhardの除去で大きく失われるというP2は**{verdict(v['P2'])}**。"
        f"変数数を除いたφとpの偏順位相関はB={f(c['phi']['B']['partial_nvars'])}、N={f(c['phi']['N']['partial_nvars'])}だった。"
        "相関は弱まらず、点推定では強まった。したがって「φが成功率を予測する主因は、この探索中のhard罰則である」という説明は支持されない。"
        "Nによる変化を、そのまま幾何の不連結性や「許容外を通らなければ解けない」ことの発見とは解釈できない。\n")
    add(f"固定診断集合の境界拒否・停止対照M1は**{verdict(v['M1'])}**。"
        f"Nには救済{pair['rescue_N']:,}開始点と喪失{pair['loss_N']:,}開始点の両方がある。"
        "この結果だけを根拠にNを完成solverの既定構成に採用したり、完成solverの費用・答え集合の回収率が改善したとは言えない。"
        "その比較はQ5の別課題である。\n")
    add("## 根拠1：何を、どの条件で測ったか\n")
    add("開発用raw-323のseed 0の**保存startそのもの**をB・N・G2に渡した。"
        "Bは凍結版、Nは `_evaluate_hard_feasibility_penalty` だけ0、G2は事前固定した距離型罰則。"
        "元の等式・guard残差・非有限時の全行置換は変えず、最終の等式・guard・hard・箱・答えの採点は共通。"
        "成功は等式ノルム≤1e-8、元条件と箱を満たし、答えが公式値のいずれかに相対許容1e-6で一致する一図である。"
        "全答えを返すことや厳密証明の成功ではない。\n")
    add(f"対象はLM272問・Powell20問。変数なし31問は対象外。元の測定で120秒打切りにより200開始点に届かなかった"
        f"{s['short_original_problems']}問もそのまま含め、開始点の補充はしなかった。"
        "今回は各開始・条件の探索deadlineを10秒とし、保存開始点を全件試した。"
        "LMのmax_nfev=80、ftol=xtol=gtol=1e-14とPowellの設定は凍結版のまま。"
        "条件順は問題番号とkで巡回し、最大4ワーカー、BLAS各1スレッド。\n")
    add(f"[事前登録](preregistration.md)のSHA256は `{audit['preregistration_sha256']}`。"
        f"新しいoptimizer呼出し前に予測・閾値・G2を固定した。固定記録から完了確認までは{start}〜{end}"
        f"（UTC、経過{elapsed/60:.1f}分、準備・中断・復元・確認を含む）。最後の問題の完了時刻は{completion['last_case_completed_utc']}。"
        f"[入力・実装の固定記録](execution-freeze.json)の{audit['unchanged_frozen_files']}ファイルは終了時も全て同じハッシュだった。"
        "基準は結果で変更していない。\n")
    add("## 根拠2：成功率と失敗・欠測\n")
    add("**実行・保存の障害もあった。** 初回実行ツールは終了コード1を返し、残ったログから終了理由は特定できなかった。"
        f"初回の完了サマリー{recovery['initial_summaries_compared']}問を保管した。"
        f"うち{recovery['counts'].get('missing_from_completed_initial_cases',0)}問・"
        f"{recovery['counts'].get('missing_from_completed_initial_rows',0):,}開始点で、完了サマリーに対応する開始点ログが欠けていた。"
        "初回途中の完了数報告はサマリー数とログ完備数を取り違えており、検出時に訂正した。\n")
    add(f"[再開手順](recovery-protocol.md)を再開前に固定し、現存する完全な行{recovery['counts']['retained_initial_rows']:,}件を保持、"
        f"残り{recovery['counts']['continuation_rows']:,}件だけを同じ座標・条件順・上限で補完／続行した。"
        f"内訳は失われた完了ログ{checks['recovery_origins']['missing_initial_log']:,}件の再計算と、"
        f"残り{checks['recovery_origins']['continuation_after_exit']:,}件の続行であり、全件の出所を確認した。"
        "solver関数は凍結したrun.solveのまま。変更したのは問題ごとのプロセス起動と、ログを毎回確定保存する処理である。"
        f"再開後のworker個別異常終了ログは{len(recovery['resume_process_failures'])}件。"
        f"初回集計と復元後のB/N/G2の分類数が全て一致したか：{'はい' if recovery['initial_counts_all_match'] else 'いいえ（差をrecovery-summary.jsonに全件記録）'}。"
        "集計が一致しても、失った初回の各終点・軌道まで一致したとは主張しない。\n")
    add("不一致はAIME-2013-II-04のNだけで、初回のleft_box 112件が復元後はleft_box 108件・timeout 4件になった。"
        "全127問で各条件のhit数は一致し、wrong_branch・wrong_answer数にも差はない。"
        f"初回127問の集計と残る165問の最終集計を組み合わせた[感度分析](recovery-sensitivity.json)でも、"
        f"P1〜P5の判定は全て{'一致した' if sensitivity['verdicts_match'] else '一致しなかった'}。"
        "失われた初回軌道を使うM1の感度分析はできない。\n")
    add("保存準備にも失敗した。再開v1はstate保存先が見つからず終了し、個別確認1回も同じ箇所で失敗した。"
        "いずれもrun.solveの前で、v1の新しい局所探索呼出しは0。v2で保存先の生成と保存時の再試行だけを加えた。"
        "作業フォルダ全体のmtime更新、HEAD変更、ファイルの一時消失も観測したが、原因は特定できなかった。\n")
    add("v2も249問の完了通知の後に実行ツールが終了コード143を返し、progress.jsonは250問で止まった。"
        "しかし問題別の完全記録は253→257→271→291→292問と増え、既存の計算が継続していることを確認した。"
        "追加のsolver起動は行わなかった。全292問・55,097行と未完了state 0を直接検査した後、"
        "通常の総括ファイルがないことを明記してrun-complete.jsonを作った。"
        "[完了確認記録](completion-reconciliation.json)を残しており、正常な終了コード0が得られたとは主張しない。\n")
    add(f"再開後の呼出し開始記録は{sum(recovery['new_call_start_records'].values()):,}回、初回を含む確認可能な呼出し数は"
        f"少なくとも{recovery['total_calls_at_least']:,}回。中断直前の未記録呼出し数は不明で、総数を確定値とはしない。"
        "補完を独立な反復として二重計上せず、各問題・各保存start・各条件を1件ずつ集計した。"
        "[保存不足と再開の監査](recovery-summary.json)、[元サマリー](initial-summaries/)、"
        "[元prefix](initial-prefixes/)を残した。\n")
    add("以下の平均は問題に同じ重みを与えた平均。hit数と失敗数は全開始点の合計であり、平均の分母とは区別する。\n")
    add("|条件|問題平均p|hit|stuck|wrong_branch|wrong_answer|left_box|error|timeout|記録欠落|\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for a in ARMS:
        cc=counts[a]
        add("|"+"|".join([a,f(p[a]),*[str(cc.get(k,0)) for k in ("hit","stuck","wrong_branch","wrong_answer","left_box","error","timeout")],str(cc.get("missing_run",0)+cc.get("missing_start",0))])+"|")
    add("\n主3条件のerror 597件は全て同じ開始点で、10問に分布し、全件が `eval_status:non_finite` だった。"
        "Sのerror 78件も同じタグで、このerror分類にはPython例外の記録はない。"
        "timeout・error・欠測はhit=0として分母に含めた。"
        "wrong_answerは有効判定を通ったが公式値との一致を確認できなかった場合（求値不能を含む）、wrong_branchは等式には到達したがguard/hard不合格、"
        "left_boxは探索箱外、stuckは等式残差が閾値を超えた場合である。"
        "これらを全て「境界で止まった」と数えてはいない。\n")
    add("wrong_answerのうち答えの数値自体が得られなかった件数は"+
        "、".join(f"{a} {checks['counts'][a+'_wrong_answer_value_missing']}件" for a in (*ARMS,"S"))+
        "。この部分も元の採点規則の分類を維持し、別の有効な答えを得たとは解釈しない。\n")
    add(f"記録された開始点組は{s['starts_observed']:,}/{s['starts_expected']:,}、全件完了問題は{s['completed_problems']}/{n}。"
        f"旧Bとの分類不一致は{pair['old_disagree']}件。Bの終点座標を比較できた{audit['counts'].get('B_old_x_comparable',0):,}件中、"
        f"{audit['counts'].get('B_old_x_exact_equal',0):,}件は座標まで完全一致した。"
        "不一致があれば[監査記録](audit.json)に開始点番号と旧・新分類を全件残した。"
        "元の120秒共有予算と今回の開始点別10秒上限が異なるので、Bの全てが旧記録と一致することを前提にはしていない。\n")
    add(f"旧Bとの分類差7件はいずれも今回のtimeoutで、そのうち旧hitは1件だった。"
        f"参考として旧Bの問題平均は{checks['old_B_problem_mean_reference']:.4f}、Nとの差は"
        f"{delta(checks['N_minus_old_B_reference'])}。主判定では事前登録どおり今回のBを用いた。\n")
    add(f"N−Bが正の問題{s['delta_counts']['positive']}、同じ{s['delta_counts']['zero']}、負{s['delta_counts']['negative']}。"
        f"0.10以上の改善は{s['delta_counts']['ge_0.10']}問、0.05以上の悪化は{s['delta_counts']['le_minus_0.05']}問。"
        f"対応する開始点で、Nは救済{pair['rescue_N']:,}・喪失{pair['loss_N']:,}、"
        f"G2は救済{pair['rescue_G2']:,}・喪失{pair['loss_G2']:,}だった。\n")
    losses=[r for r in csv.DictReader((HERE/"transitions.csv").open())
            if r["pair"]=="B_to_N" and r["from"]=="hit" and r["to"]!="hit"]
    add("Nで失われた開始点の行き先は"+"、".join(f"{r['to']} {int(r['count']):,}件" for r in losses)+
        "。別枝・別答だけでは、喪失の大半を説明できなかった。\n")
    add("|出発点の元hard判定|保存開始点数|B当たり数／割合|N当たり数／割合|G2当たり数／割合|\n"
        "|---|---:|---:|---:|---:|")
    for F,label,column in (("True","F（許容）","nF"),("False","I（不許容）","nI")):
        denom=sum(int(r[column]) for r in rows)
        cells=[]
        for a in ARMS:
            hit=sum(g.get("hit",0) for g in s["group_counts"] if g["arm"]==a and g["start_F"]==F)
            cells.append(f"{hit:,}／{hit/denom:.4f}" if denom else "欠測")
        add("|"+"|".join([label,f"{denom:,}",*cells])+"|")
    add("\nこのF/I表は開始点を合算した割合であり、問題等重みの主平均ではない。"
        f"F開始点が0の問題は{sum(int(r['nF'])==0 for r in rows)}問、I開始点が0の問題は{sum(int(r['nI'])==0 for r in rows)}問。"
        f"出発時のF/I判定が不明な開始点は{checks['counts']['start_F_unknown']}件。"
        "存在しない開始群の条件付き成功率を0として補っていない。\n")
    both=[r for r in rows if int(r['nF']) and int(r['nI'])]
    add(f"F/Iの両方が存在する{len(both)}問だけの問題等重みの記述集計は次のとおり（追加の成立判定には使わない）。\n")
    add("|条件|平均pF|平均pI|pF<pIの問題数|\n|---|---:|---:|---:|")
    for a in ARMS:
        mf=sum(float(r['pF_'+a]) for r in both)/len(both)
        mi=sum(float(r['pI_'+a]) for r in both)/len(both)
        ni=sum(float(r['pF_'+a])<float(r['pI_'+a]) for r in both)
        add(f"|{a}|{mf:.4f}|{mi:.4f}|{ni}/{len(both)}|")
    add("")
    add("|層|問題数|B平均|N平均|G2平均|N−B|\n|---|---:|---:|---:|---:|---:|")
    for key,label in (("LM","LM"),("Powell","Powell"),("original_200","元から200開始点"),("G2_no_boolean_guard","G2に真偽値guardなし")):
        z=s["strata"][key]
        add("|"+"|".join([label,str(z["n"]),*[f(z["means"][a]) for a in ARMS],delta(z["delta_N"]["mean"])])+"|")
    add("\nLM/Powell別等は適用範囲を見るための併記であり、主判定の分母292問を置き換えない。\n")
    add("## 根拠3：固定した予測の判定\n")
    pb,pn=(c["phi"][a]["partial_nvars"] for a in ("B","N"))
    hb,hn=(c["human"][a]["spearman"] for a in ("B","N"))
    rt,rf=bad["True"],bad["False"]
    add("|予測|事前の判定基準|観測|判定|\n|---|---|---|---|")
    add(f"|P1|平均Δ≥0.03、95%下端>0、Δ≥0.10が30問以上|平均{f(d['mean'])}、下端{f(d['ci95'][0])}、{s['delta_counts']['ge_0.10']}問|{verdict(v['P1'])}|")
    add(f"|P2|abs(偏rho_N)<0.15、偏rho_B−偏rho_N≥0.20|{f(pn)}、差{f(pb-pn) if pb is not None and pn is not None else '欠測'}|{verdict(v['P2'])}|")
    add(f"|P3|0.05以上の悪化が5〜20%、Rの悪化率≥非Rの2倍、悪化問題の過半で別枝・別答増加|{bad['bad_n']}/{n}={100*bad['bad_fraction']:.1f}%、R {rt['bad_n']}/{rt['n']} 対 非R {rf['bad_n']}/{rf['n']}、別枝・別答増加{bad['bad_wrong_increase']}/{bad['bad_n']}|{verdict(v['P3'])}|")
    add(f"|P4|平均ΔN>0のときΔG2/ΔNが0.25〜1.25|比={f(s['ratio_G2'])}、G2−B={f(s['delta_G2']['mean'])}|{verdict(v['P4'])}|")
    add(f"|P5|人間難度とのabs(rho_N)<0.20、Bとの差<0.10|rho B={f(hb)}、N={f(hn)}、差={f(hn-hb) if hb is not None and hn is not None else '欠測'}|{verdict(v['P5'])}|")
    add("\nRは新結果を見ずに、旧rawのwrong_branch+wrong_answer≥10%、非等号guard、交点の選択・除外チェックのいずれかで固定した70問。"
        "結果を見て悪化問題が多くなるよう付け替えてはいない。wrong_answerだけで退化や枝の誤りを確定することはできない。\n")
    add(f"P3では悪化割合10.3%だけは予測範囲内だったが、R/非Rの悪化率比は{rt['rate']/rf['rate']:.2f}倍で2倍に届かず、"
        "別枝・別答が増えたのも悪化30問中8問だった。予告した悪化の型は十分に当たらなかった。\n")
    add("## 根拠4：φ、人間難度との関係\n")
    add("|指標|観測問題数／欠測|B順位相関|N順位相関|G2順位相関|B偏相関|N偏相関|G2偏相関|\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|")
    for key,label in (("phi","保存startのφ"),("phi_independent","独立1024点のφ（感度分析）"),("human","人間難度human")):
        z=c[key]
        add("|"+"|".join([label,f"{z['n']}／{z['missing']}",*[f(z[a]["spearman"]) for a in ARMS],*[f(z[a]["partial_nvars"]) for a in ARMS]])+"|")
    add("\n偏相関は各量の順位から変数数の順位との線形関係を除いた残差間相関。"
        "人間難度の空欄は補完せず、共通の実測問題だけを比較した。"
        "独立φは既存astra-consult-13の測定を使用した。これは未使用問題での外部検証ではない。"
        "人間の思考過程は測っておらず、人間とsolverの難しさの本質的な違いを証明したものではない。\n")
    add("## 根拠5：境界での拒否と停止条件の切り分け\n")
    den=m.get("F_B_fail_N_hit",0)
    wall=m.get("rescue_with_wall_reject",0)
    sh=m.get("rescue_also_S_hit",0)
    add("診断対象は、各問題の保存順で最初のF最大10点・I最大10点。3,973開始点のうち、LM3,729点には"
        "B/N/G2に加えてSを実行した。Sは元のhardを残しnativeのftol=gtolだけ0にする。xtolと機械精度停止は残す。"
        "Powell244開始点ではこのMINPACK診断は非適用で、欠測と混同しない。\n")
    add(f"固定LM診断集合のFでB失敗→N成功は{den}組。そのうちBにF→I・等式＋guard二乗和下降・hard増加の"
        f"**同一試行での拒否**を観測したのは{wall}/{den}（{100*wall/den:.2f}%）、Sでも成功したのは{sh}/{den}。"
        f"Nが途中のI点を受理していたのは{m.get('rescue_N_accepted_I',0)}/{den}。"
        f"M1（前者80%以上、Sでの救済10%以下）は**{verdict(v['M1'])}**。"
        "78.85%を80%以上へ丸めたり、閾値を下げたりはしない。境界拒否は多くの救済例で観測されたが、予告した割合には達しなかった。"
        "この分母を全55,097開始点の救済数へ読み替えない。\n")
    add(f"全LM診断開始点でBとSの最終分類が異なったのは{m.get('B_S_class_disagree_all_diagnostic',0)}件。"
        "この4件はいずれも失敗分類どうしの変化で、成功／失敗の入替えは0件だった。"
        "受理／拒否はnativeへ渡すfun/jacの記録から次のjac基点・返却座標を使って推定したもので、MINPACK内部フラグの直接取得ではない。"
        "同一座標の試行は受理・拒否を判別せずunknownにした。\n")
    add("|条件|診断実行|native未完了|trace欠落|不整合run|unknown試行|\n|---|---:|---:|---:|---:|---:|")
    for a in (*ARMS,"S"):
        add("|"+"|".join([a,*[str(m.get(a+k,0)) for k in ("_expected_trace","_incomplete_trace","_missing_trace","_issue_runs","_unknown_trials")]])+"|")
    add("\n公開statusとraw infoは[status.csv](status.csv)、問題別の救済機構は[mechanism-by-problem.csv](mechanism-by-problem.csv)、"
        "末尾8試行は[records/](records/)に保存した。Sで変化が小さくても、定数成分の丸め・減少比や差分尺度を含む"
        "全ての数値的影響が否定されたとは言えない。またNは不許容側の1e4段差だけでなく、許容側の余裕の逆数項も消す。"
        "従ってNによる改善全てを境界拒否の因果効果とは呼ばない。\n")
    add("## 根拠6：G2で実際に比較できた範囲\n")
    gc=s["g2_counts"]
    boolean=sum(value for key,value in gc.items() if key.startswith("boolean:"))
    fallback=sum(value for key,value in gc.items() if key != "calls" and not key.startswith("boolean:"))
    add("G2はguardの違反量と非退化・選択の余裕不足の二乗和平方根をhard関数に返す。元の係数10を残す。"
        "比較式・bound等では制約式の値に比例する傾きがあるが、座標空間の最短距離ではない。"
        "hinge・max/min・作図の枝があり、全域で微分可能な方法ではない。元guard行との重複重みもある。\n")
    add(f"G2罰則関数の評価は{gc.get('calls',0):,}回。真偽値述語の評価項は{boolean:,}回、"
        f"その他の距離取得不可・例外等のカウンタ合計は{fallback:,}（項・理由の重複を含む）。"
        f"真偽値処理または例外代替を含む評価が現れたのは{s['audit'].get('g2_fallback_runs',0):,}開始点、"
        f"{s['audit'].get('g2_fallback_cases',0)}問。静的には59問に真偽値guardがある。"
        "[g2-fallbacks.csv](g2-fallbacks.csv)に種類別回数を残した。作図不能で等式が非有限になる点は元の全行1e10のままである。\n")
    add(f"G2の問題平均は{p['G2']:.4f}、G2−Bは{delta(s['delta_G2']['mean'])}。"
        f"問題ごとのNとG2の差の絶対値の平均は{s['mean_abs_G2_N']:.4f}だった。"
        "この1設計の成績を、一般の滑らかな制約法や適応的penalty全体の成績とみなしてはいけない。\n")
    add("## 個別例（結果による説明用の抽出）\n")
    add("以下はΔNの上位・下位各5問であり、予測の対象を選ぶための表ではない。全292問は[per-problem.csv](per-problem.csv)。\n")
    add("|問題|開始点数|方式|B|N|G2|N−B|R群|\n|---|---:|---|---:|---:|---:|---:|---|")
    sorted_rows=sorted(rows,key=lambda r:(float(r["delta_N"]),r["id"]))
    shown=[]
    for rr in (list(reversed(sorted_rows[-5:])), sorted_rows[:5]):
        for r in rr:
            if r["id"] in shown:
                continue
            shown.append(r["id"])
            add("|"+"|".join([r["id"],r["n"],r["method"],*[f(float(r["p_"+a])) for a in ARMS],delta(float(r["delta_N"])),"○" if r["risk"]=="True" else "—"])+"|")
    add("\nGで取り上げた例の今回の結果は次のとおり。Gの予備実験の別seed・40点ずつとは開始点が違い、今回はseed 0の保存点全件である。\n")
    add("|問題|F開始点数|FのB／N／G2|I開始点数|IのB／N／G2|\n|---|---:|---:|---:|---:|")
    by_id={r["id"]:r for r in rows}
    for cid in ("AIME-2010-II-14","HMMT-2022-FEB-GEO-03","HMMT-2007-FEB-GEO-06","HMMT-2007-FEB-GEO-04","JMO-2017-PRE-01"):
        r=by_id[cid]
        values={group:"／".join(f(float(r["p"+group+"_"+a])) if r["p"+group+"_"+a] else "欠測" for a in ARMS) for group in ("F","I")}
        add(f"|{cid}|{r['nF']}|{values['F']}|{r['nI']}|{values['I']}|")
    add("\n## 費用、再現性、残る限界\n")
    add("|条件|時間記録のある実行数|局所実行秒の合計|1開始の中央値秒|残差評価数合計|\n|---|---:|---:|---:|---:|")
    for a in (*ARMS,"S"):
        cc=s["costs"][a]
        add(f"|{a}|{cc['n_timed']:,}|{cc['sum_seconds']:.1f}|{cc['median_seconds']:.4f}|{cc['sum_evaluations']:,}|")
    add("\nこの時間は診断対象のtrace取得・最終採点を含む局所実行時間。入力準備や結果書込等を含む全体の壁時計とは異なる。"
        "保存不足に対する補完行では再開後の時間を使っており、初回だけの費用ではない。初回の失われた時間・軌道は復元できなかった。"
        "10秒は探索のdeadlineで、最後の採点等のオーバーヘッドにより実測時間が少し超えることがある。"
        "診断集合の計測オーバーヘッドがあるので、完成solverの速度比較としては使わない。\n")
    add("本検証は既知の開発292問・既存seed 0の同じ開始点による対照実験。新seed・未知問題での一般化は未測定。"
        "95%区間はこの問題集合を単位に10,000回再標本化したもので、未知の全幾何問題についての保証ではない。"
        "未観測の成功領域や全ての答えの回収も評価していない。\n")
    add("文献との関係は[既存Gの文献節](../../strategy/astra-consult-17/G/answer.md)と"
        "[相談17](../../strategy/gpt-pro-consult-17-answer.md)を背景にした。非許容な中間点を許す制約処理やpenalty自体を新発見とはしない。"
        "今回はネットワークでの追加文献調査を実施しておらず、既存法への新規性・優位性を新たに確認したわけではない。\n")
    add(f"指定Pythonを使用し、環境変更・インストール・src編集・commit・pushなし。"
        f"最大成果物は{audit['largest_file_bytes_and_name'][0]/1024**2:.2f}MiBで、数十MBを超える単一ファイルはない。"
        f"[保存由来の最終監査](final-checks.json)では、保持した初回{checks['counts']['retained_rows_verified']:,}行の不変性、"
        "292問の完全記録と控えの一致、再開コード・計画のハッシュを確認した。"
        "準備段階の人工guard評価でcontext不足が2回発生し、optimizerを一度も走らせる前にテスト入力を修正した。"
        "[deviations.md](deviations.md)に記録し、実験結果の失敗数とは分けた。再現手順は[README.md](README.md)。\n")
    (HERE/"answer.md").write_text("\n".join(q))
    print("Wrote final answer.md from completed summary and audit.")


if __name__ == "__main__":
    main()
