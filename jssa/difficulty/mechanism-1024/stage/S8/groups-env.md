# 群と環境変数の固定

実装：`/tmp/mechanism-7b-lkdjle5l/final`（BASE1）、source_hash `sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3`。BASE0=60db4b6＋既存WinPC ablation patch＋new-switches.patch。ソース変更なし。

`runtime/ablation.py:18–19` は値が文字列 `1` と完全一致した場合だけ停止。configs.json では停止= `1`、有効= `0` を8変数すべてに明示する。全 GEOSOLVER_* 継承値を除去して適用する。未設定も有効だが、今回の固定表では曖昧さを避けて0を使う。

| 群 | 環境変数（接頭辞 GEOSOLVER_ABLATE_） | 停止 / 有効 | 確認した実効範囲 |
|---|---|---|---|
| G1 探索 | `NO_NOMAD` | 1 / 0 | 通常・hybrid探索のNOMAD importをImportErrorにし、SciPy多点出発にfallbackする。scalar scan、有限guard、整数候補は残る。救済の別PyNomad importは止まらない。 |
| G2 第2探索・救済 | `NO_SECOND_ATTEMPT` / `NO_RESCUE` | 1 / 0 | 第2attempt descriptorを除き、救済の条件分岐を止める。救済には失敗/不足・残時間8秒以上等の条件がある。有効化しても毎回発火しない。 |
| G3 候補選択 | `NO_DIVERSE_SELECTION` | 1 / 0 | 各search→refinementバッチを有限な生残差ノルムの上位20にする。同一candidate_uidだけ統合し、座標距離除去・seed枠なし。通常backendの適格/fallback poolは維持。救済は実装上adapter.records全件が母集団で、従来の各箱上位6限定ではない。主探索の初期点/救済箱の多様性は残る。 |
| G4 残差書き換え・尺度座標 | `NO_RESIDUAL_REWRITE` / `NO_SCALE_CHART` | 1 / 0 | 精密化の距離0座標差・接条件・正半径補助行を止め、残差の平滑化が必要な解析Jacobian計画も拒否する。最終検証の書き換えは維持。尺度chart候補の生成も別スイッチで止める。 |
| G5 代数的前処理 | `NO_ALGEBRAIC` | 1 / 0 | 通常primaryのsearch_algebraic_branches入口のみ停止。尺度chartからsymbolic workerへの直接要求、整数近道・離散補完・PSLQは止めない。allow_algebraicフラグ自体をFalseにはしない。 |
| G6 解析Jacobian | `NO_ANALYTIC_JAC` | 1 / 0 | closure用derivative_planをNoneにして数値微分へ戻す。LMの数値Jacobianは元から残る。NO_RESIDUAL_REWRITEが1でもrequires_smoothing=Falseの計画は利用可能。 |

各コード位置（以下 src/geosolver/engine/standard/ 相対）：
- G1：`search/nomad_backend.py:42-46`、`orchestration/run_search.py:372-395,447-494`
- G2：`orchestration/run_external_pipeline.py:196-234,454-479`
- G3：`orchestration/run_external_pipeline.py:408-416`、`search/residual_selection.py:8-36`、`orchestration/run_rescue_search.py:79,136-149`
- G4：`refinement/mpmath_refiner.py:1028-1040,1337-1374`、`search/scale_chart.py:13-44`、`orchestration/run_search.py:518-534`
- G5：`search/algebraic_branches.py:656-679`、`orchestration/run_external_pipeline.py:346-357,406,557-576`
- G6：`refinement/analytic_jacobian.py:162-183`、`refinement/mpmath_refiner.py:1020-1049`

`GEOSOLVER_ABLATE_SEARCH_MODE` は BASE1 全src本文に読込み実装がなく、設定しても効かないので使用しない。設定オブジェクトの global_search_mode は `disco_mads` / `mads` / `scipy_multistart` / `hybrid_legacy_nomad` を受け付けるが、今回の環境変数切替では既定 disco_mads を維持し NO_NOMAD のfallbackを使う。救済は別の既定 mads。

## 依存関係と残る経路

- G1 off → G2 rescue：NO_NOMADは通常backendだけ。G2がonなら救済MADSは使用可能。N+2でも救済PyNomadが動きうる。 根拠：`search/nomad_backend.py:43`、`orchestration/run_rescue_search.py:27-33,69,112-124`
- G1 off → G1 backend replacement：SciPy多点出発へfallback。ただし1変数scalar scanや整数/有限guard近道の早期返却は残るため、全問がSciPyを通るとは限らない。 根拠：`orchestration/run_search.py:337-370,447-494`
- NO_SCALE_CHART=1 → NO_RESIDUAL_REWRITE：尺度chart候補生成と精密化残差書き換えは独立。片方の停止で他方は停止しない。G4では両方を同時に停止。通常の残差/列/行スケーリングは残る。 根拠：`search/scale_chart.py:14`、`refinement/mpmath_refiner.py:1356`
- NO_RESIDUAL_REWRITE=1 → G6：requires_smoothing=Trueの解析計画だけ拒否する。G6 onのN+6は平滑化不要な解析計画だけ使用可能。 根拠：`refinement/mpmath_refiner.py:1028-1040`
- NO_ANALYTIC_JAC=1 → G4：解析計画を全停止するが、残差書き換えや尺度chartを止めない。G4 on/G6 offでも書き換え残差の数値微分が使える。 根拠：`refinement/analytic_jacobian.py:163`、`refinement/mpmath_refiner.py:1356`
- NO_ALGEBRAIC=1 → G4 scale chart：独立。尺度chartは_eligibleを再利用しsymbolic requestを直接呼ぶため、G5 offでもG4 onなら代数workerを使いうる。 根拠：`search/scale_chart.py:19,32-44`、`search/algebraic_branches.py:658`
- G2 off → G1/G3/G4/G5/G6：第2attemptと救済で追加される候補/残時間/呼出機会を消す。主探索と主精密化は独立に残る。 根拠：`orchestration/run_external_pipeline.py:223,455`
- G5 on → G1/G3/G4 scale chart：代数prepassが結果を返すとalgebraic_search or run_searchにより通常探索・尺度chartを迂回する。その後の候補選択と精密化は実行される。 根拠：`orchestration/run_external_pipeline.py:355-357,393-408`

Nは指定された6群の全停止である。ただし入力による変数削減、初期probe、制約スケーリング、整数/有限guard/1変数scan、数値LM・closure、最終検証とその式変換/補正、PSLQ等は残る。「あらゆる工夫を除いた数値最適化」とは解釈しない。特にG4は実装に合わせた精密化側の停止であり、最終検証は凍結版と同一（nrr-final-check.md）。

## 12構成

完全な8変数集合は configs.json。`N+1 = C1` はaliasのみで重複実行しない。

| 構成 | 有効な群 |
|---|---|
| N | なし |
| N+2 | G2 |
| N+3 | G3 |
| N+4 | G4 |
| N+5 | G5 |
| N+6 | G6 |
| C1 | G1 |
| C2 | G1, G2 |
| C3 | G1, G2, G3 |
| C4 | G1, G2, G3, G4 |
| C5 | G1, G2, G3, G4, G5 |
| BASE | G1, G2, G3, G4, G5, G6 |

短時間動作確認の実測は smoke-check.md/json。登録されたflagと分岐到達、実際に利用したbackend、未到達の機構を区別する。
