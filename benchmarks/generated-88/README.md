# 追加評価用の生成88入力

2026-10-11の高速化追試で凍結した、11構造族 × 4パラメータ × 2等価表現の入力集合です。
自然問題323問とは別に評価します。パラメータ・等価表現は従属した標本であり、88の独立した問題族とは数えません。

| 構造族 | 検査する構造 |
|---|---|
| `symmetric_cubic` | 対称多項式系と根の置換 |
| `hyperbola_section` | 双曲線と直線の交点・複数の目標値 |
| `ellipse_section` | 楕円と直線の交点 |
| `parabola_circle` | 放物線と円の交点・4根 |
| `singular_sum_squares` | 特異なJacobianと冗長条件 |
| `signed_norm` | 距離と符号条件 |
| `tangent_line_circle` | 直線と円の接点 |
| `right_incircle_scale` | 内接円による尺度の固定 |
| `periodic_target` | 周期的な解集合と一定の目標値 |
| `rational_hole` | 分母の禁止点 |
| `oriented_similarity_target` | 配置の自由度と不変な面積比 |

## 入力と来歴

- `cases.jsonl`と`dsl/`：既存runnerに渡せる入力・参照答。
- `derivations.json`：各入力の正解集合の数学的導出、構造族、パラメータ・等価表現の対応。
- `freeze.json`：当時の凍結記録をバイト単位で保存したもの。
- `manifest.json`：取り込み後のファイルhash、件数、変更点。

取り込みでは各caseに`problem_kind: generated`だけを追加しました。DSL・参照答・導出は変更していません。
元のcases・生成コード・高速化の採否資料は、[experiment側の記録](https://github.com/kabatan/geosolver/tree/experiment/research-archives/solver-evidence/optimization-speed-20261011)に保存しています。

当時の最終報告は`first_solve_performed: false`です。開発選抜を通った変更がなかったため求解を行わず保持しました。
今回の取り込みでも静的検証だけを行い、solverは実行していません。現在のsolverの成績は未測定です。

## 検証と評価

静的検証は求解せず、公開DSLへの適合と入力ファイルの対応を確認します。
`unique_natural_problem_count`は0、`generated_input_count`は88になります。

```bash
uv run python benchmarks/research_runner.py validate --cases benchmarks/generated-88/cases.jsonl
```

初回評価の前に比較する実装・seed列・採否基準を固定し、結果を見た後は開発データとして扱ってください。
実行する場合は、空の新しい出力先を指定します。既定の323問の結果とは分け、構造族ごとの結果と等価表現間の差も確認します。

```bash
uv run python benchmarks/research_runner.py run benchmarks/local-evaluation/generated-88-v1 --cases benchmarks/generated-88/cases.jsonl --jobs 8 --seeds 0
uv run python benchmarks/research_runner.py assess benchmarks/local-evaluation/generated-88-v1 --cases benchmarks/generated-88/cases.jsonl
uv run python benchmarks/research_runner.py summarize benchmarks/local-evaluation/generated-88-v1
```

参照答は採点にだけ使います。既存runnerはworker要求・生の求解記録へ参照答を渡しません。
180秒／問題・1物理コア／jobの実行条件は323問と共通です。
