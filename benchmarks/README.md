# GeoSolver benchmark cases

このディレクトリは、スクリーンショット由来の幾何ベンチマーク問題を保存する。

## 配置

- `cases.jsonl`: 1問題につき1行のJSONオブジェクト。空行、コメント、JSONLのヘッダーは置かない。
- `dsl/<id>.json`: `GeometryProblem` 公開スキーマに従う実行用DSL。`cases.jsonl` の `dsl_path` から相対参照する。

## JSONLレコード

```json
{
  "id": "case-0001",
  "problem_statement": "問題文を原文どおりに記録",
  "instructions": {
    "free_variables": ["t"],
    "construction": ["スクリーンショットの作図手順を意味が変わらない粒度で記録"],
    "target": "求める量を原文どおりに記録"
  },
  "dsl": {
    "id": "case-0001",
    "variables": ["t"],
    "constructions": [],
    "conditions": [],
    "target": "..."
  },
  "dsl_path": "dsl/case-0001.json",
  "rating": 1,
  "answer": "正解を原文どおりに記録",
  "source": "出典を原文どおりに記録"
}
```

`dsl` はJSONL内にも完全な内容を持たせ、`dsl_path` のファイルと一致させる。`rating` の尺度は、ユーザーから別指定がない限り 1（易）〜10（難）とする。`source` はURLに限らず、書籍名・ページ・コンテスト名などを記録できる。

## 追記ルール

1. 既存行は編集・並べ替えせず、重複しない `id` の新しい1行を末尾に追加する。
2. DSLファイル名も `id` から決め、JSONLの `dsl` とファイル内容を一致させる。
3. DSLは `GeometryProblem` の公開形式（`variables`、`constructions`、`conditions`、`target`）を使い、内部の旧形式を保存しない。
4. 問題文、自由変数、構成手順、細かい条件、求める量、rating、答え、出典を省略しない。
5. 追記後は `uv run geosolver validate benchmarks/dsl/<id>.json` で検証する。
