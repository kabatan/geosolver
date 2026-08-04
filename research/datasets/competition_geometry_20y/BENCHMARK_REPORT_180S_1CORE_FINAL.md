# 最終DSL後の性能測定（180秒 / 1 core）

これは `experiment` branch の最終DSLに対する測定結果です。圧縮前の履歴baselineは [`BENCHMARK_REPORT_180S_1CORE.md`](BENCHMARK_REPORT_180S_1CORE.md) に残し、ここでは最終修正後の評価だけを扱います。

## 条件

```text
runtime: /home/kabatan/work/solver-experiment-runtime
seed: 7
budget: 180秒
外側hard timeout: 180秒
jobs: 1
CPU affinity: [0]
```

全302ファイルのfresh subprocess測定を完了し、AIME-2016-I-15だけは、後述の作図修正を反映した同条件の再実行行に置き換えています。他の301行は全件測定のraw出力を保持しています。

## 集計

| status | 件数 |
|---|---:|
| `success` | 232 |
| `no_solution` | 36 |
| `timeout` | 13 |
| `exception` | 4 |
| `reference_only` | 17 |
| **合計** | **302** |

公開解答がある実行対象は206件です。answer projection（AIMEの整数化を含む）と数値比較を再計算した結果は次のとおりです。

| 判定 | 件数 | 分母 |
|---|---:|---:|
| 代表解が期待値に一致 | 165 | 206 |
| 期待値集合を全て含む（coverage） | 128 | 206 |
| 余分な候補なしの厳密集合一致 | 115 | 206 |
| coverageのみ（余分な候補あり） | 13 | 206 |

contest別の代表解一致は AIME 73、HMMT 83、JMO予選 9 です。

## DSL修正の確認

AIME-2016-I-15では、原文が「ωとω₂のもう一つの交点を `C≠B`」と指定しているのに、旧DSLが `YD` と ω₂の交点として `C` を作っていたため、退化枝 `C=B` が残っていました。最終DSLでは

```text
C = Intersect(omega, omega2, exclude=B)
```

とし、`D≠A` と `C≠B` もguardに明記しました。修正後の180秒/1 core再実行は `AB²=270` でした。

最終結果に残る6件の代表解不一致は、DSLに任意のεを追加せず、原文どおりの厳密不等号を保った結果 solver が退化極限を受理したものです。

- HMMT-2006-FEB-GEO-10: `r→0`（原文は半径 `r>0`）。
- HMMT-2013-FEB-GEO-04: `Ay→0`（交点が接線上へ退化）。
- HMMT-2014-FEB-GEO-09: `r4→0`。
- HMMT-2023-FEB-GEO-02: `u` または高さが0へ近づく枝。
- HMMT-2024-FEB-GEO-03: 非直径条件 `h≠0` に対する `h→0`。
- HMMT-2024-FEB-GEO-10: `P`を通る四辺形がほぼ一直線になる枝（面積guardの数値許容）。

これらに `>0.01` のような問題文にないマージンを戻すと誤採択は隠せますが、解集合を変更するためDSL修正とは扱っていません。

## 採点器の修正

幾何定義は変更せず、評価だけを次のように修正しました。

- Phase Cに exact symbolic value がある場合は小数fallbackより先に使う。
- `quadratic_radical_radicand` は `(231-3√989)/10` のような有理係数を許容する。
- 公開解答の `sqrt(33)` 表記を `√33` と同じように数値評価する。

これにより、AIME-2007-I-15、AIME-2014-II-11、JMO-2019-MATHNET-08ya/JMO-2019-PRE-10 の採点上の取りこぼしをDSL不備と混同しなくなりました。

## 再現・検証

- raw/final結果: [`benchmark_results_180s_1core_final.json`](benchmark_results_180s_1core_final.json)
- 最終結果validator: [`validate_benchmark_180_final.py`](validate_benchmark_180_final.py)
- DSL全件validator: [`verify_dsl_integrity.py`](verify_dsl_integrity.py)

最終validatorは `302/302` coverage、status集計、answer-set判定、CPU affinity `[0]` を確認します。
