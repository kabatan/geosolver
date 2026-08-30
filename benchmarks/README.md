# GeoSolver benchmark cases

`cases.jsonl`と`dsl/`が現行入力の唯一の定義元です。過去の大量の実行結果・一時診断・旧DSL生成器はこのブランチへ移植していません。
`provenance/`と`repairs/`は出典と修正の監査用であり、そこに保存した旧DSL・削除済みの登録は実行対象に含めません。

## 研究用runner

件数の根拠は`research_runner.py validate`の機械出力です。現在はinventory 323、実行可能323、参照確認済み323、参照保留0、参照のみ0、移行保留0、自然問題323です。現行セットには重複登録がありません。

`HMMT-2013-FEB-GEO-09` は通常角による条件系の矛盾が確認され、公式の訂正も特定できなかったため、2026-08-30にユーザーの指示で現行の`cases.jsonl`と`dsl/`から削除しました。削除前の登録・埋込DSL・公表答えは[監査用記録](repairs/corpus97/removed-cases.jsonl)へ保全し、再生成時も現行セットへ復活させません。過去の実験結果は変更していません。[公式資料の再確認と削除記録](repairs/corpus97/HMMT_2013_GEO_09_SOURCE_CHECK.md)を参照してください。

同日にHMMTの別名3件・JMOのMathNet由来3件も重複除去しました。公式問題番号付き・一次出典の登録を残し、solver成績を選択基準にはしていません。残した323登録のDSL・条件順・参照集合は変更していません。[対応表と削除記録](repairs/dedup-20260830/README.md)に元の6登録とhashを保全しています。

旧未完成・参照未確認の97件は[修復記録](repairs/corpus97/README.md)に原文照合・数学的検算・変更理由を残して復元しました。HMMT 2011の同一直線問題は原文が許す別配置を含め、参照を`{7,35/11}`としています。実行可能・参照確認済みは「solverが解ける」という意味ではありません。

```bash
uv run python benchmarks/research_runner.py validate
uv run python benchmarks/research_runner.py run benchmarks/local-evaluation/new-campaign --jobs 8 --seeds 0
uv run python benchmarks/research_runner.py assess benchmarks/local-evaluation/new-campaign
uv run python benchmarks/research_runner.py summarize benchmarks/local-evaluation/new-campaign
```

runは180秒・1 coreで固定し、Linuxでは異なる物理coreのCPUへjobを割り当てます。出力先は空であることが必要です。再実験には新しい名前を使い、古いcampaignを上書きしません。

参照値はraw runに入れません。manifestの参照hashと一致する参照を使い、別工程のassessでcanonical exact key集合を比較します。未確認の参照値は正誤判定から除外します。

`local-evaluation/`はGit追跡対象外です。実行後はそのディレクトリと`SHA256SUMS`を別途保全してください。
以前の実行結果は元の作業ツリーに残っています。移植前の`solver-a0-canary-20260830`は全jobが同じCPUへ固定されていたため、時間を正式な性能評価へ使いません。

`stress_runner.py`はLinuxの負荷診断専用です。例えば8物理core・16並列の過剰割当を再現できますが、専有1 coreの正式な性能値とは比較しません。通常の研究実行には`research_runner.py`を使います。

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

1. 通常の追加では既存行を編集・並べ替えず、重複しない `id` の新しい1行を末尾に追加する。誤りの修復では旧行を保存し、旧新hash・理由・根拠を修復台帳へ残して同じIDを訂正する。過去artifactは変更しない。
2. DSLファイル名も `id` から決め、JSONLの `dsl` とファイル内容を一致させる。
3. DSLは `GeometryProblem` の公開形式（`variables`、`constructions`、`conditions`、`target`）を使い、内部の旧形式を保存しない。
4. 問題文、自由変数、構成手順、細かい条件、求める量、rating、答え、出典を省略しない。
5. 追記後は `uv run geosolver validate benchmarks/dsl/<id>.json` で検証する。
