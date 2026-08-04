# Raw exact solution-set benchmark report

## 判定の変更

今回の採点では、contest の最終入力形式を正答とはみなさない。各 DSL の
`answer` 式が表す量を `exact_truth.jsonl` に raw target として保持し、solver の
Phase C が返した `phasec.answer_values` と、次の双方向条件で比較する。

\[
  \{\text{solver が返した厳密値}\}
  =
  \{\text{問題文と DSL の厳密解集合}\}.
\]

したがって、例えば本文が「量を既約分数 `a/b` で表し `a+b` を答えよ」と
指定する場合、`exact_answer_set` は `a/b`、`presentation_answer` は `a+b` である。
`a+b` を DSL から出させたり、採点時に `post_process` で復元したりしない。

記号式は SymPy で簡約して比較するが、数値許容幅で別の値を同一視しない。
Phase C が同じ記号解に付随して出す小数シリアライズだけは重複として除外する。
記号値を伴わない小数出力は厳密解集合とは認めない。

## 実験条件

- branch: `experiment`
- 対象: DSL 302 files（実行可能 285、`reference_only` 17）
- seed: 7
- 制限: 180 秒 hard timeout、1 job、CPU 0 固定
- 入力: `benchmark_results_180s_1core_after_general_fix_final.json`
- 再採点結果: `benchmark_results_180s_1core_strict_raw.json`

solver 実行そのものは既存の 180 秒測定を使用し、JMO-2016-PRE-03 は、問題文が
角度を度で尋ねることを DSL の `answer = 180*Angle(...)/pi` に反映した後に同条件で
再実行した。

## 結果

truth の状態を混ぜないため、正答率の主分母は `truth_status=verified` かつ
実行可能な 205 件とした。

| 指標 | 件数 |
|---|---:|
| 全 DSL | 302 |
| 実行可能 | 285 |
| solver 成功 | 259 |
| 独立に raw truth を確認済み | 205 |
| raw truth が未解決（unknown） | 91 |
| raw truth はあるが `reference_only` | 6 |
| 厳密解集合が完全一致 | **139 / 205 (67.80%)** |
| 成功した verified run に限った完全一致 | **139 / 195 (71.28%)** |
| truth 集合をすべて含む（余分な候補は許す） | 148 / 205 |
| truth を含むが余分な候補もある | 9 |

未解決 91 件は、solver の出力を正答として流用せず、`unknown` のまま分母から
除外した。従って 302 件全体に対して 139/302 と表示するのも、91 件を誤答と
みなすのも不適切である。

### contest 別（verified runnable のみ）

| contest | verified runnable | 厳密集合一致 | 成功かつ厳密一致 |
|---|---:|---:|---:|
| AIME | 95 | 71 (74.74%) | 71 |
| HMMT | 95 | 62 (65.26%) | 62 |
| JMO | 15 | 6 (40.00%) | 6 |
| 合計 | 205 | **139 (67.80%)** | **139** |

### verified 205 件の不一致内訳

| 分類 | 件数 | 判定上の意味 |
|---|---:|---|
| 厳密集合一致 | 139 | 正答 |
| 小数のみ（数値的に近い） | 35 | 数値近似は出ているが、厳密集合一致ではない |
| truth を含むが余分なexact枝がある | 9 | coverageはあるが完全解集合ではない |
| truth exact + 小数の余分な候補 | 5 | 小数は厳密解集合の要素ではない |
| exact式だが別の値／別の集合 | 5 | 厳密比較で不一致 |
| 小数のみで別の値 | 2 | 厳密比較で不一致 |
| `no_solution` | 7 | 解集合を返していない |
| timeout | 2 | 制限時間内に解集合を返していない |
| exception | 1 | 実行例外 |

## 旧採点との比較について

旧レポートの `181/206` は、contest の掲載解答形式や代表解を使う採点であり、
今回の定義とは対象が異なる。特に `a+b`、`100a+b`、根号内の整数などへの変換を
成功扱いしていたため、raw geometric quantity の解集合一致を表していない。
旧集計は履歴比較用に残すが、solver の数学的な正答率としては今回の strict raw
集計を使用する。

## 監査・再現

次の検査はすべてエラー 0 で完了している。

```bash
python3 build_exact_truth.py

PYTHONPATH=/home/kabatan/work/solver-experiment-runtime/geosolver/src \
  /home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  verify_dsl_integrity.py \
  --benchmark benchmark_results_180s_1core_strict_raw.json

/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  validate_strict_benchmark.py \
  --benchmark benchmark_results_180s_1core_strict_raw.json

/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  build_failure_case_audit.py

/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  verify_failure_case_independent.py > FAILURE_CASE_INDEPENDENT_CHECKS.json
```

`verify_dsl_integrity.py` は全 302 DSL と truth ledger の source hash、IR parse、
変数数、answer metadata 混入を検査する。`validate_strict_benchmark.py` は benchmark
の全行について raw Phase C 値から採点を再計算し、`reported_answer` が存在しない
こと、180 秒・1 core 条件、summary 集計との一致を独立に検査する。
記号式の再計算には固定 solver runtime の SymPy を使う（system Python に SymPy が
ない場合でも、近似値を厳密値へ昇格させることはない）。

66件の不一致をcase単位で、raw値・DSL全文・source hash・guards/constraints・runtime
証拠と突合した結果は `FAILURE_CASE_AUDIT_STRICT_RAW.md` にまとめ、機械可読な全証拠は
`FAILURE_CASE_AUDIT_STRICT_RAW.jsonl` に保存した。生成とcoverage検査は
`build_failure_case_audit.py` が行う。
