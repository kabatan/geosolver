# 失敗35件の再測定（180秒・1 core）

## 対象と条件

前回の `benchmark_results_180s_1core_after_refiner_fix_failed66.json` で
`answer_set_exact=false` だった35件だけを、修正後DSLで再実行した。対象の
`case_id` は結果JSONの `case_id_filter` に固定している。

- branch: `experiment`
- seed: `7`
- solver budget: 180秒
- hard timeout: 有効
- jobs: 1
- CPU affinity: `[0]`（1 core固定）
- truth: 35/35件が `truth_status=verified`
- runtime: `/home/kabatan/work/solver-experiment-runtime`（変更なし）

## 集計

| 指標 | 件数 |
|---|---:|
| 対象 / 実行 | 35 / 35 |
| `success` | 29 |
| `no_solution` | 3 |
| `timeout` | 3 |
| exception | 0 |
| 厳密解集合一致 (`answer_set_exact`) | **1 (2.9%)** |
| 完全解集合 (`answer_set_complete`) | 8 (22.9%) |
| 正答を含むが余分な解あり | 7 (20.0%) |

厳密解集合一致は `HMMT-2021-FEB-GEO-05` の `49/400` だけである。
これは今回修正したDSLが、元の問題の解集合と一致することを確認できたケースである。

## 再測定で確認できた不一致の型

- 高精度の小数だけが返る（例: `72.000…`, `10/3` の小数表現）ため、厳密式との集合比較に失敗。
- 正しい解に加えて退化・境界枝が残る（例: `HMMT-2007-FEB-GEO-04` の `7`,
  `HMMT-2013-FEB-GEO-04` の `1`, `HMMT-2024-FEB-GEO-03` の `246`）。
- `no_solution` は3件、180秒での `timeout` は3件だった。
- `JMO-2019-MATHNET-08yk` と `JMO-2019-PRE-08` は同じ数値的な三次根
  `9*CRootOf(128*x**3 - 80*x**2 + 7*x - 1, 0)` を返し、truthの
  `(81 + 9*sqrt(13))/16` と一致しなかった。

## 結果ファイル

機械可読な全35件のraw結果は
`benchmark_results_180s_1core_failed35_after_dsl_fixes.json` に保存している。
この再測定ではDSLやsolver runtimeを追加変更していない。
