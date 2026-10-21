# 2026年新規問題（未使用評価集合）

HMMT February 2026（Geometry 10問・Guts 7問）とJMO 2026予選（3問）の平面幾何の求値問題20問です。
solverを60db4b6で凍結した後に、原文だけからDSLを書きました。DSL作成・検算の間、GeoSolverの求解は一度も実行していません。

| ファイル | 内容 |
|---|---|
| `statements.jsonl` | 収集した原文・公式の答え・図の情報（解答・解説は参照していない） |
| `authoring-rules.md` | DSL化の前に固定した規則（許す操作・禁止する操作・監査） |
| `build_cases.py` | DSL・参照答・原文との対応表の単一の定義元 |
| `cases.jsonl`, `dsl/` | runnerに渡す入力と参照答 |
| `mapping.json`, `AUDIT.md` | 条件ごとの対応表、DSL、検算ログをまとめた監査表 |
| `verify/` | 独立検算ツールとログ |

AIME 2026は問題文を取得できていないため含めていません。

## 検算

`verify/check_dsl.py`はGeoSolverの探索を使わず、DSLの評価層（構成・残差・guard・目標式）だけを使います。
SciPyの多点開始最小二乗で実行可能な配置を集め、60桁のGauss-Newtonで精密化してから、目標値の集合を公式の答えと比べます。
20問すべてで公式の答えを与える配置が見つかり、公式以外の値は退化配置（三角形が潰れるもの）だけでした。
多点開始は網羅性を保証しないため、「公式以外の答えを許さない」ことの証明ではありません。

```bash
uv run python benchmarks/research_runner.py validate --cases benchmarks/new-2026/cases.jsonl
uv run python benchmarks/new-2026/verify/run_all.py HMMT-2026-FEB-GEO-01 300 0
```

## 評価

結果を見た後でDSLを直さないでください。直す必要が出た場合は別版として記録します。

```bash
uv run python benchmarks/research_runner.py run benchmarks/local-evaluation/new-2026-v1 --cases benchmarks/new-2026/cases.jsonl --jobs 8 --seeds 0
```
