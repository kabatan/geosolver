# exactification factor fix: decimal-only 10件の再測定

## 実行条件

- 対象: `BENCHMARK_AFTER_MPMATH_REFINER_FIX_FAILED66.md` の `decimal_only_near_exact` 10件
- seed: `7`
- 予算: `180 s / case`
- CPU: `taskset -c 0`、`jobs=1`、`--require-one-core`
- hard timeout: 有効
- strict判定: Phase C の raw `answer_values` と `exact_truth.jsonl` の `exact_answer_set` の一致（presentation answer・post-process不使用）
- 修正版runtime: `/home/kabatan/work/solver-experiment-runtime-exactfix`
- 生データ: [benchmark_results_180s_1core_exactification_factor_fix_decimal10_2026-08-12.json](benchmark_results_180s_1core_exactification_factor_fix_decimal10_2026-08-12.json)

## 結果

| 指標 | 修正前（同じ10件の既存測定） | 修正後 |
|---|---:|---:|
| 実行 | 10 | 10 |
| `success` | 10 | 10 |
| `timeout` / `no_solution` / `exception` | 0 / 0 / 0 | 0 / 0 / 0 |
| strict exact set一致 | **0** | **0** |

したがって、今回の一般的な「repeated/reducible PSLQ relationを最小因子へ正規化し、根距離でも検証する」修正による、decimal-only 10件の strict 正答率の改善は **0件** だった。

## exactificationの直接診断

再測定の Phase C 値を `identify_answer(..., input_precision_dps=120)` に再投入した結果は次の通り。検証許容誤差は実装上 `10^-(120-20) = 1e-100` である。

| case | 期待厳密値 | PSLQ/フォールバックの結果 | 検証残差の目安 |
|---|---|---|---:|
| AIME-2009-I-05 | `72` | `(1,-72)` を発見するが `verification_failed` | `2.87e-88` |
| AIME-2015-II-11 | `18/5` | `(5,-18)` を発見するが `verification_failed` | `4.62e-84` |
| AIME-2016-I-06 | `10/3` | `(3,-10)` を発見するが `verification_failed` | `2.16e-84` |
| AIME-2022-II-11 | `180` | PSLQ/フォールバックとも `not_identified` | `4.25e-39` |
| HMMT-2006-FEB-GEO-03 | `31` | `(1,-31)` を発見するが `verification_failed` | `1.20e-87` |
| HMMT-2006-FEB-GEO-04 | `27π/40` | `not_identified` | — |
| HMMT-2008-FEB-GEO-03 | `π-2` | `not_identified` | — |
| HMMT-2010-FEB-GEO-01 | `3π/7` | `not_identified` | — |
| HMMT-2013-FEB-GEO-05 | `-1/8` | `(8,1)` を発見するが `verification_failed` | `2.23e-85` |
| HMMT-2023-FEB-GEO-01 | `189` | `(1,-189)` を発見するが `verification_failed` | `7.96e-89` |

つまり整数・有理数の6件は正しい線形関係自体は見つかっているが、数値候補の実効誤差が `1e-100` より大きいため、修正版検証器が厳密値へ昇格させず拒否している。`π` を含む4件は、数値だけを入力する現在の PSLQ/根検証経路では厳密な `π` 表現を同定できない。

## 解釈

この修正の目的は、近似値 `72+ε` を `(x-72)^2` の残差の小ささだけで `72` と誤認することを防ぐことであり、`72` へ丸めることではない。したがって、今回の10件が decimal のまま残ったことは、修正が無効だった証拠ではない。むしろ、平方因子による誤った厳密化を許さず、十分な精度のない近似を strict exact として受理しなかった結果である。

なお、HMMT-2008-FEB-GEO-03 は修正前後で rejection tag が `status_not_allowed:branch_instability` から `margin_too_small` に変化したが、accepted raw value は依然 `π-2` の数値近似で、strict結果は不一致のままである。
