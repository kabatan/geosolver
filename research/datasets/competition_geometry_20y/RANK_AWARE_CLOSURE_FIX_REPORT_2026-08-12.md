# Rank-aware high-precision closure 一般修正

## 結論

decimal-onlyだった整数・有理数6件の共通原因は、問題ごとのDSLではなく、残差方程式が
変数より少ないときに高精度closureを無条件で停止するsolver実装だった。さらに、方程式数と
変数数が同じでもJacobianに冗長方向がある場合、従来のfull-system `findroot`は特異行列で
失敗していた。

この2つを、問題IDや期待解を参照しないrank-aware closureで一般修正した。対象6件は
180秒/1 core再測定で **6/6 strict exact answer-set一致**となった。構造的rank欠損の
追加対照 `AIME-2015-II-11` も **1/1** 一致した。

## 一般修正の内容

1. closure開始点で高精度有限差分Jacobianを作る。
2. 完全ピボットGauss消去により、独立なsource residual行と、それを局所的に解ける変数列を
   同数選ぶ。
3. 選ばれなかった変数はclosure開始値に固定し、局所座標chart上で正方な部分系を解く。
   これはglobal rotationやline方向scaleなどのgaugeを一つ選ぶだけであり、DSLへ条件を追加
   する処理ではない。
4. Newton部分系が収束しても、その部分系だけでは受理しない。元のevaluatorで全source
   residualを再評価し、全残差normがstage target以下、bounds内、全hard guard feasibleの
   場合だけclosure成功とする。不整合な未選択制約が1つでも残ればfail closedする。
5. pipelineのmonotonic deadlineを各closure残差評価まで伝播し、rank-aware fallbackを
   64反復に制限した。これにより任意のunder-determined候補が残り時間を独占しない。

変更箇所は `mpmath_refiner.py` とその回帰テストだけである。DSL、truth、answer projection、
post-process、exactifierの許容誤差は変更していない。

## 180秒 / 1 core 再測定

共通条件はseed 7、hard timeout 180秒、jobs=1、`taskset -c 0`、affinity `[0]`、
`one_core_enforced=true`。正答はpresentation answerではなく、Phase C raw
`answer_values`と監査済み厳密解集合の一致で判定した。

| case | 期待厳密集合 | Phase C厳密集合 | wall秒 | strict exact |
|---|---:|---:|---:|---:|
| AIME-2009-I-05 | `{72}` | `{72}` | 101.796 | yes |
| AIME-2016-I-06 | `{10/3}` | `{10/3}` | 100.612 | yes |
| AIME-2022-II-11 | `{180}` | `{180}` | 147.298 | yes |
| HMMT-2006-FEB-GEO-03 | `{31}` | `{31}` | 100.581 | yes |
| HMMT-2013-FEB-GEO-05 | `{-1/8}` | `{-1/8}` | 55.404 | yes |
| HMMT-2023-FEB-GEO-01 | `{189}` | `{189}` | 57.380 | yes |

集計はsuccess 6、strict exact 6、timeout 0、no_solution 0、exception 0。
生データは
[`benchmark_results_180s_1core_rank_aware_closure_six_2026-08-12.json`](benchmark_results_180s_1core_rank_aware_closure_six_2026-08-12.json)
に固定した。

`AIME-2015-II-11` は4変数・4制約だが、固定済み距離の恒等制約とline方向scaleの冗長性が
あり、従来は全closure stageでsingular matrixとなった。追加対照では59.670秒、Phase C
厳密集合 `{18/5}`、strict exact一致だった。生データは
[`benchmark_results_180s_1core_rank_aware_closure_square_control_2026-08-12.json`](benchmark_results_180s_1core_rank_aware_closure_square_control_2026-08-12.json)
である。

## 安全性と回帰

専用回帰では以下を独立に検証した。

- 1方程式・2変数のunder-determined系を局所chartで閉じられる。
- 方程式数=変数数でも冗長行を持つ系を閉じられる。
- 選ばれた部分系だけが解け、未選択の元制約が不整合なら必ず拒否する。
- deadline後には`findroot`を開始しない。
- 従来のstep-convergence偽陽性、bounds、全残差certificationを維持する。

検証結果:

- closure + exactification focused tests: **14 passed**
- geosolver全suite: **136 passed, 1 skipped**
- Ruff: pass
- `compileall`: pass
- patch dry-run: exactfix runtimeへclean apply

## 再現物

修正版runtimeは `/home/kabatan/work/solver-experiment-runtime-rankfix`。元のfrozen runtime、
strictfix runtime、exactfix runtimeは変更していない。SHA256は
[`runtime_rank_aware_closure_fix_manifest.json`](runtime_rank_aware_closure_fix_manifest.json)、
再適用diffは
[`runtime_rank_aware_closure_fix.patch`](runtime_rank_aware_closure_fix.patch) に固定した。

exactfix runtimeを基点として次で再適用できる。

```bash
patch --binary -p1 < runtime_rank_aware_closure_fix.patch
```

artifactとruntime hash、1-core測定条件、7件の厳密集合一致は
`verify_rank_aware_closure_fix.py`で機械検証できる。
