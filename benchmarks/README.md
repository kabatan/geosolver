# GeoSolver benchmark cases

`cases.jsonl`と`dsl/`が現行入力の唯一の定義元です。過去の実行結果・一時診断・旧DSL生成器・修復用資料は通常の作業ツリーへ置きません。

## 研究用runner

件数の根拠は`research_runner.py validate`の機械出力です。現在はinventory 323、実行可能323、参照確認済み323、参照保留0、参照のみ0、移行保留0、自然問題323です。現行セットには重複登録がありません。

旧未完成・参照未確認97件の修復後、条件矛盾のある`HMMT-2013-FEB-GEO-09`と重複6登録を除去しました。重複の代表は公式問題番号・一次出典で選び、solver成績は使用していません。HMMT 2011の同一直線問題は原文が許す別配置も含め、参照を`{7,35/11}`としています。実行可能・参照確認済みは「solverが解ける」という意味ではありません。

旧抽出資料・修復前DSL・削除記録はcommit `c30f97d9`のGit履歴から確認できます。
`cases.jsonl`内の`migration`・`repair`は当時の来歴情報です。`repair.ledger`などのパスは同commitの`benchmarks/`からの相対パスであり、現在の実行時依存ではありません。

```bash
git show c30f97d9:benchmarks/repairs/corpus97/repair-ledger.jsonl
```

```bash
uv run python benchmarks/research_runner.py validate
uv run python benchmarks/research_runner.py run benchmarks/local-evaluation/new-campaign --jobs 8 --seeds 0
uv run python benchmarks/research_runner.py assess benchmarks/local-evaluation/new-campaign
uv run python benchmarks/research_runner.py summarize benchmarks/local-evaluation/new-campaign
```

runは180秒・1 coreで固定し、Linuxでは異なる物理coreのCPUへjobを割り当てます。出力先は空であることが必要です。再実験には新しい名前を使い、古いcampaignを上書きしません。

参照値はraw runに入れません。manifestの参照hashと一致する参照を使い、別工程のassessでcanonical exact key集合を比較します。未確認の参照値は正誤判定から除外します。

`local-evaluation/`はGit追跡対象外です。実行後はそのディレクトリと`SHA256SUMS`を別途保全してください。
以前の実行結果はrepo外の保全ディレクトリへ移しました。[作業場所と旧資料](../README.md#作業場所と旧資料)を参照してください。移植前の`solver-a0-canary-20260830`は全jobが同じCPUへ固定されていたため、時間を正式な性能評価へ使いません。

`stress_runner.py`はLinuxの負荷診断専用です。例えば8物理core・16並列の過剰割当を再現できますが、専有1 coreの正式な性能値とは比較しません。対象は`--all`（参照確認済みの実行可能問題すべて）または繰り返し指定できる`--case-id`で明示します。固定60問の自動選定は行いません。通常の研究実行には`research_runner.py`を使います。

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

1. 通常の追加では既存行を編集・並べ替えず、重複しない `id` の新しい1行を末尾に追加する。誤りの修復では理由・根拠をGitの変更記録に残して同じIDを訂正する。旧入力はGit履歴で保全し、過去artifactは変更しない。
2. DSLファイル名も `id` から決め、JSONLの `dsl` とファイル内容を一致させる。
3. DSLは `GeometryProblem` の公開形式（`variables`、`constructions`、`conditions`、`target`）を使い、内部の旧形式を保存しない。
4. 問題文、自由変数、構成手順、細かい条件、求める量、rating、答え、出典を省略しない。
5. 追記後は `uv run geosolver validate benchmarks/dsl/<id>.json` で検証する。
