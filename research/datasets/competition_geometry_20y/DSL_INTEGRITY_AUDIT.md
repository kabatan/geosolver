# DSL完全性監査（最終）

## 機械検査

`verify_dsl_integrity.py --benchmark benchmark_results_180s_1core_final.json` の結果:

```json
{
  "audit_rows": 548,
  "dsl_files": 302,
  "inventory_ready_paths": 302,
  "runnable_files": 285,
  "reference_only_files": 17,
  "errors": 0,
  "variable_histogram": {"0":43,"1":40,"2":62,"3":55,"4":51,"5":23,"6":17,"7":11}
}
```

各JSONについて、重複キー拒否付きJSON parse、ID/filename一致、変数名重複、7変数上限、construction名重複、constraints/guardsの型、空の `source_statement`/`clause_ledger`、answer metadataの混入、production IR parserを検査しています。`manual_audit.jsonl` の `source_statement` と `clause_ledger` も現行JSONへ同期済みです。

## 意味監査で修正した最後の不備

### AIME-2016-I-15

原文の `ω` と `ω₂` の交点 `C≠B` を、旧版は `Line(Y,D)` と ω₂の交点として構成していました。この構成では `C=B` の退化枝が残ります。最終版は `C=Intersect(omega,omega2,exclude=B)` とし、`D≠A`/`C≠B` のstrict guardも保持しています。原文の `C,Y,D` 共線はconstraintとして残っています。

### 既存監査で修正済みの代表例

- 点が線分・辺の内部にある条件を `OnSegment`/`OnLine(...,ordered=True)` として明示。
- 交点の「もう一つ」「minor arc」「ray」の枝を `exclude`、`near`、順序・内外guardで表現。
- `acute`、`convex`、内部点、同側/反対側、面積二分、正方形の任意順序を原文どおりに保持。
- HMMT-2025-FEB-GEO-02の「some order」は対角/反対点条件に修正。
- 問題文にない `0.01`、`0.001`、`0.1`、`0.05` の数値マージンを削除し、厳密な `>0`/`≠0` に戻した。

## 不備とsolver数値挙動の分離

最終測定で残る6件の不一致は、全て原文のstrict条件を満たす正しい枝も `phasec.answer_values` に含んでいます。先頭に選ばれた値だけが、面積0・半径0・非直径の極限などへ数値的に寄っています。したがって、これらに任意のepsilonを追加することはDSLの意味を変えるため実施していません。

`reference_only` 17件は、図の順序・内外などを現行IRへ勝手に補うと意味が変わるため、原文と台帳を保持したまま未実行にしています。これはDSL欠落ではなく、表現不能な条項を捏造しないための明示的な境界です。

## 実行コマンド

```bash
PYTHONPATH=/home/kabatan/work/solver-experiment-runtime/geosolver/src \
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
research/datasets/competition_geometry_20y/verify_dsl_integrity.py \
--benchmark research/datasets/competition_geometry_20y/benchmark_results_180s_1core_final.json

/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
research/datasets/competition_geometry_20y/validate_benchmark_180_final.py
```
