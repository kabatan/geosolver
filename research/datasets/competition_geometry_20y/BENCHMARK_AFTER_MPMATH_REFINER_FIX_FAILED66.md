# 失敗66ケースの再実行結果（mpmath refiner修正後）

## 実行条件

- 対象: `FAILURE_CASE_AUDIT_STRICT_RAW.jsonl` に記録された、修正前に strict exact set が不一致だった66件
- seed: `7`
- budget: `180 s / case`
- CPU: `taskset -c 0`、`jobs=1`、`one_core_enforced=true`
- hard timeout: 有効
- strict判定: Phase CのDSL raw answer setと `exact_truth.jsonl` の厳密解集合を比較（presentation answerやpost-processは不使用）
- solver runtime: `/home/kabatan/work/solver-experiment-runtime`
- 結果JSON SHA-256: `26960fc6f74b96c6a1249acd68875dac5dc4ae693eef070e26b0ffb146203e35`

## 集計

| 指標 | 件数 |
|---|---:|
| 対象 / 実行 | 66 / 66 |
| `success` | 59 |
| `no_solution` | 3 |
| `timeout` | 4 |
| `exception` | 0 |
| strict exact set一致 | **31** |
| strict exact set不一致 | 35 |
| 全実行のwall time合計 | 3174.15 s |

修正前に失敗していた66件のうち **31件 (47.0%)** が、今回のsolver修正だけで厳密解集合一致に復帰した。復帰したケースでは、正答表示用の整数化やpost-processを正誤判定に用いていない。

## strict exactへ復帰した31件

`AIME-2006-I-07`, `AIME-2006-II-09`, `AIME-2009-II-10`, `AIME-2011-I-14`, `AIME-2013-II-04`, `AIME-2013-II-08`, `AIME-2015-II-15`, `AIME-2019-I-06`, `AIME-2022-I-03`, `AIME-2022-II-07`, `AIME-2023-II-09`, `AIME-2025-II-12`, `HMMT-2006-FEB-GEO-01`, `HMMT-2006-FEB-GEO-06`, `HMMT-2006-FEB-GEO-07`, `HMMT-2007-FEB-GEO-02`, `HMMT-2008-FEB-GEO-02`, `HMMT-2008-FEB-GEO-07`, `HMMT-2012-FEB-GEO-01`, `HMMT-2014-FEB-GEO-08`, `HMMT-2016-FEB-GEO-04`, `HMMT-2020-FEB-GEO-02`, `HMMT-2022-FEB-GEO-05`, `HMMT-2024-FEB-GEO-05`, `HMMT-2024-FEB-GEO-07`, `HMMT-2025-FEB-GEO-08`, `JMO-2019-MATHNET-08ya`, `JMO-2019-PRE-10`, `JMO-2022-MATHNET-08z4`, `JMO-2022-PRE-04`, `JMO-2022-PRE-12`

修正前の監査カテゴリ別の復帰数は次の通り。

| 修正前カテゴリ | 対象 | 復帰 |
|---|---:|---:|
| `decimal_only_near_exact` | 34 | 24 |
| `decimal_only_refinement_error` | 1 | 1 |
| `target_exact_plus_decimal_extra` | 5 | 1 |
| `target_plus_extra_exact` | 9 | 2 |
| `no_solution` | 7 | 2 |
| `wrong_exact_branch` | 5 | 1 |
| `hard_timeout` | 2 | 0 |
| `wrong_decimal_branch` | 2 | 0 |
| `runtime_exception` | 1 | 0 |

## 依然としてstrict不一致の35件

以下は「solver修正後も不一致」という意味であり、DSLの不備とsolverの未解決問題を混同しないため、修正前監査カテゴリを併記している。

- `decimal_only_near_exact` (10): `AIME-2009-I-05`, `AIME-2015-II-11`, `AIME-2016-I-06`, `AIME-2022-II-11`, `HMMT-2006-FEB-GEO-03`, `HMMT-2006-FEB-GEO-04`, `HMMT-2008-FEB-GEO-03`, `HMMT-2010-FEB-GEO-01`, `HMMT-2013-FEB-GEO-05`, `HMMT-2023-FEB-GEO-01`
- `target_exact_plus_decimal_extra` (4): `AIME-2011-II-02`, `AIME-2020-I-01`, `HMMT-2013-FEB-GEO-04`, `HMMT-2021-FEB-GEO-05`
- `target_plus_extra_exact` (7): `AIME-2014-II-08`, `AIME-2018-I-04`, `HMMT-2007-FEB-GEO-04`, `HMMT-2010-FEB-GEO-09`, `HMMT-2014-FEB-GEO-09`, `HMMT-2018-FEB-GEO-05`, `HMMT-2024-FEB-GEO-03`
- `wrong_exact_branch` (4): `HMMT-2014-FEB-GEO-10`, `HMMT-2023-FEB-GEO-02`, `HMMT-2023-FEB-GEO-04`, `HMMT-2024-FEB-GEO-10`
- `wrong_decimal_branch` (2): `HMMT-2006-FEB-GEO-10`, `HMMT-2015-FEB-GEO-04`
- `no_solution` (5): `AIME-2018-II-12`, `AIME-2020-II-15`, `AIME-2021-I-13`, `JMO-2019-MATHNET-08yk`, `JMO-2019-PRE-08`
- `hard_timeout` (2): `AIME-2020-II-13`, `JMO-2015-PRE-11`
- `runtime_exception`から状態変化後も未解決 (1): `JMO-2013-PRE-08`（今回は exception ではなく timeout）

状態遷移は、旧 `no_solution` 7件のうち4件が `success` になり、そのうち2件が strict exact に復帰した。一方、旧 `runtime_exception` の `JMO-2013-PRE-08` は例外を抑止できたが、180秒内に解を得られず timeout になった。また旧 `success` の `HMMT-2007-FEB-GEO-04` は今回 timeout となった。

## 生データ

全66件のcaseごとのstatus、raw Phase C answer values、rejection tags、wall time、strict判定は次のJSONに保存している。

- `benchmark_results_180s_1core_after_refiner_fix_failed66.json`

