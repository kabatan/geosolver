# 答えの出どころの集計（再実行なし）

元データ: 凍結版の本計測 `jssa-main-j6-20261022`（323問 × seed 0/1/2 = 969回）の各問の結果JSON（`diagnostics.pipeline_summary`）。再実行はしていません。

## 方法

- 「採用された答えを出した段階」は、`answer_source_candidate_id` に対応する `candidate_uid` の先頭2要素から決めました。対応は、コード（60db4b6）の `origin_backend` で確認しています。
  - `search/exact_polynomial` → 代数的前処理（`algebraic_branches.py`、`origin_backend="exact_polynomial"`）
  - `search/nomad` → Phase A の探索（NOMAD）
  - `search/scipy` → LM法の多点出発（scipy）
  - `rescue/nomad` → rescue
  - `direct/constant` → 変数0の経路
  - `search/positive_scale_chart`、`search/finite_guard_local`、`search/integer_square_difference` → それぞれ同名の補助探索
- `integer_closure_derived` は、uid に `integer_closure`（整数への閉包。整数フォールバックの印）が含まれるかどうかです。
- 各段階の時間は `phase_timings`、第2探索は `search_staged_fallback`、失敗の段階は assessment の `failure_stage` です。
- 列の詳細は `attribution.csv` の見出しを参照してください。

## 段階ごとの件数（969回）

| 答えの出どころ | 件数 | 正解 | 問題数 | wall中央値(秒) | search | refinement | exact_assembly | rescue |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Phase A の探索（search/nomad） | 476 | 465 | 170 | 12.82 | 1.22 | 3.85 | 5.01 | 0.0 |
| 代数的前処理 | 292 | 292 | 99 | 1.53 | 0.0 | 0.06 | 0.16 | 0.0 |
| 変数0の経路 | 93 | 93 | 31 | 1.26 | 0.0 | 0.0 | 0.47 | 0.0 |
| LM法の多点出発（scipy） | 74 | 74 | 32 | 3.34 | 0.88 | 0.12 | 0.84 | 0.0 |
| rescue | 25 | 21 | 18 | 123.43 | 1.52 | 62.79 | 31.83 | 2.85 |
| positive_scale_chart | 3 | 3 | 1 | 17.48 | 0.86 | 11.06 | 4.10 | 0.0 |
| 整数の平方差の走査 | 3 | 3 | 1 | 5.07 | 0.46 | 2.83 | 0.79 | 0.0 |
| finite_guard_local | 3 | 2 | 1 | 83.51 | 14.03 | 14.13 | 54.05 | 0.0 |

## 読み取れること

- 代数的前処理と変数0の経路だけで、969回中385回（約40%）の答えが出ています。時間の中央値は約1.5秒以下です。「NOMADが主役」とは言いにくい構成です。
- NOMAD が答えを出したのは476回（約49%）です。時間の中央値は12.8秒で、全体の中央値（5.2秒）より長い問題が多いです。
- rescue が答えを出したのは25回（21正解）で、時間の中央値は123秒と非常に長い問題です。seed 0 のアブレーションで rescue を止めても正解が減らなかった（319問）ことと整合します。rescue は最後の手段として少数の問題だけで働いています。
- 第2探索が動いたのは38回で、そのうち fallback が選ばれたのは32回（31回が正解）です。
- 答えの出どころが seed によって変わった問題は28問です。
- 失敗した16回のうち、9回が最終検証（`final_verification`）、1回が同定（`exactification`）での失敗です。そのほかに、正解扱いにならなかった「余分な答え」が2回、「欠けた答え」が14回あります（set_relation の `extra` と `missing`）。

## 注意

- `search/scipy` を「第2探索（fallback）」の産物とは言い切れません。1変数の問題などで、primary の中で scipy の探索が使われた例が60回あります（fallback は14回）。
- 精密化・同定・最終検証のどこで失敗したかは、`failure_stage` のほか、`exact_numeric_feasible`・`exact_accepted`・`exact_rejected_false_positive` で見られます。
