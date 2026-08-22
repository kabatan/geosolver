# 全302件再測定（2026-08-22）

## 結論

最新の結合runtimeを用いて、全302 DSLをseed 7、各ケース180秒hard timeout、1 job、CPU affinity `[0]`で最初から最後まで再実行した。手作業で厳密解集合を確定した205件に対する集合完全一致は **190/205 = 92.68%** だった。

`status=success`だけでは正答とせず、Phase Cの`answer_values`と`exact_truth.jsonl`の厳密解集合を双方向の記号集合一致で比較した。`post_process`、contestのpresentation answer、数値許容幅は採点に使用していない。

## 実行条件

- branch / solver source: `experiment`、`32bd715c0b80bd10bbd551a56fe17dfb8f004bb2`
- runtime: `/home/kabatan/work/solver-experiment-runtime-piaffinefix`
- seed: `7`
- budget: `180.0`秒 / case
- runner: 1 job、hard timeout有効
- CPU affinity: `[0]`、one-core enforcement有効
- DSL: 302 files（実行可能285、reference-only 17）
- truth: verified 205、未検証91

## 厳密正答率

| contest | verified | 厳密集合一致 | 不一致 | 正答率 |
|---|---:|---:|---:|---:|
| AIME | 95 | 87 | 8 | 91.58% |
| HMMT | 95 | 90 | 5 | 94.74% |
| JMO予選 | 15 | 13 | 2 | 86.67% |
| **合計** | **205** | **190** | **15** | **92.68%** |

verified 205件のstatusはsuccess 192、timeout 10、no_solution 3だった。success 192件のうち190件が厳密集合一致で、残る2件はsuccessだが解集合不一致である。

全302件のrunner statusは次のとおり。

| status | 件数 |
|---|---:|
| success | 252 |
| timeout | 21 |
| no_solution | 12 |
| reference_only | 17 |
| exception | 0 |

truth未検証91件は正答率の分母から除外した。この91件には、solverが値を返したケース、timeout/no_solution、現行IRで安全に実行できないreference-onlyが含まれる。

## verified不一致15件

| case | status | wall秒 | 厳密解集合 | 観測 |
|---|---|---:|---|---|
| `AIME-2007-I-15` | timeout | 180.106 | `231/10 ± 3√989/10` | Phase Cなし |
| `AIME-2015-I-07` | timeout | 180.106 | `539` | Phase Cなし |
| `AIME-2017-II-10` | timeout | 180.106 | `546` | Phase Cなし |
| `AIME-2018-II-12` | no_solution | 131.265 | `112` | 20候補を`residual_too_large`で棄却 |
| `AIME-2018-II-14` | timeout | 180.107 | `168/59` | Phase Cなし |
| `AIME-2020-II-13` | timeout | 180.106 | `60` | Phase Cなし |
| `AIME-2020-II-15` | no_solution | 20.643 | `717` | 1候補を`residual_too_large`で棄却 |
| `AIME-2021-I-13` | no_solution | 5.982 | `672` | `answer_missing` / `residual_non_finite` |
| `HMMT-2008-FEB-GEO-09` | timeout | 180.105 | `75/64` | Phase Cなし |
| `HMMT-2014-FEB-GEO-10` | success / mismatch | 72.816 | `1235/108` | decimal `11.435180724…` 1個を受理。厳密値`11.435185185…`とは不一致 |
| `HMMT-2015-FEB-GEO-04` | success / mismatch | 21.208 | `37/76` | decimal 9個（約0.4954--0.7296）を受理し、厳密targetを含まない |
| `HMMT-2024-FEB-GEO-01` | timeout | 180.106 | `5/3` | Phase Cなし |
| `HMMT-2024-FEB-GEO-08` | timeout | 180.106 | `64(2-√3)` | Phase Cなし |
| `JMO-2013-PRE-08` | timeout | 180.108 | `12` | Phase Cなし |
| `JMO-2015-PRE-11` | timeout | 180.106 | `288/35` | Phase Cなし |

したがって、今回のverified失敗は、timeout 10件、候補が残らないno_solution 3件、successだが厳密解集合不一致2件に分かれる。余分な厳密解だけを含む`target_plus_extra`型は0件だった。

## 所要時間

実行可能285件の`wall_sec`合計は14,069.10秒（3時間54分29秒）、平均49.37秒、中央値31.44秒、p90 132.22秒、p95 180.106秒、最大180.111秒だった。

success 252件だけでは合計9,385.60秒、平均37.24秒、中央値25.46秒、p90 85.87秒、最大177.99秒だった。`JMO-2019-MATHNET-08yk`は177.41秒、`JMO-2019-PRE-08`は177.50秒で成功しており、180秒枠が直接必要なケースを含む。

## 旧full run・暫定合成値との比較

旧strict full runの139/205（67.80%）に対し、今回は190/205（92.68%）で、**+51件 / +24.88 percentage points** となった。case単位では旧runの失敗から58件が成功へ変わり、旧runで成功していた次の7件が今回はtimeoutへ変わった。

- `AIME-2007-I-15`（旧76.04秒）
- `AIME-2015-I-07`（旧121.75秒）
- `AIME-2017-II-10`（旧35.52秒）
- `AIME-2018-II-14`（旧69.38秒）
- `HMMT-2008-FEB-GEO-09`（旧89.91秒）
- `HMMT-2024-FEB-GEO-01`（旧130.34秒）
- `HMMT-2024-FEB-GEO-08`（旧143.96秒）

会話中の196/205（95.6%）は、複数の対象ケース再実行を既存full runへ合成した暫定値であり、単一の連続full runではない。今回のfull runは同一条件で302件を連続実行し、上記7件の同時timeoutも含めているため、現時点の再測定値としては190/205を正とする。なお、以前余分な解を返していた5ケース（`HMMT-2007-FEB-GEO-04`、`HMMT-2013-FEB-GEO-04`、`HMMT-2024-FEB-GEO-10`、`JMO-2019-MATHNET-08yk`、`JMO-2019-PRE-08`）は今回すべて厳密集合一致した。

## 検証と成果物

- raw full run: `benchmark_results_180s_1core_latest_full_2026-08-22.json`
  - SHA-256: `4777219c4aef12ce41b44302b8ba8a45c9fe41624c62dd1731a604a98c4925b3`
- strict rescored: `benchmark_results_180s_1core_latest_full_strict_2026-08-22.json`
  - SHA-256: `5a46bceaa2f8cabc96821dc35b2c913946ba4a7879ec5f2f9af93bc701d852bf`

`validate_strict_benchmark.py`は302件のcoverage、180秒・1 core metadata、全行のtruth/presentation/solution集合、summary再集計を検査して`errors=0`だった。`verify_dsl_integrity.py`も302 DSL、548 audit/inventory rows、0--7変数制約、benchmark coverageを検査して`errors=0`だった。

今回runnerが出す現行フィールドと旧strict validatorの互換性を保つため、`rescore_strict_benchmark.py`はpresentation answerを入力の旧`expected_answer`からコピーせず、監査済み`exact_truth.jsonl`から復元するよう修正した。これは採点値を変更する処理ではなく、現行形式を旧strict schemaへ正規化するための一般的な互換修正である。
