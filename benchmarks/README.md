# GeoSolver benchmarks

実行契約と開発手順は[README](../README.md)と[REQUIREMENTS.md](../REQUIREMENTS.md)を参照してください。

幾何ベンチマークでは`cases.jsonl`と`dsl/`が現行入力の定義元です。過去の実行結果・一時診断・修復用資料は通常の作業ツリーへ置かず、`benchmarks/local-evaluation/`（Git対象外）を使います。

監査で見つかった問題を直したDSLの別版は[dsl-revisions](dsl-revisions/README.md)にあります（323問の凍結版は変えていません）。

追加評価用に[生成88入力](generated-88/README.md)も保持しています。11構造族のパラメータ・等価表現であり、自然問題323問とは別の集合です。`--cases benchmarks/generated-88/cases.jsonl`で既存runnerを使えます。取り込み時点では静的検証のみで、求解成績は未測定です。

GMBとの比較準備には[GMB独立実行環境](gmb/README.md)を使います。GeoSolverの依存環境とは分離し、公式GMBと専用venvをGit対象外の領域に置きます。比較入力の監査・原典情報・整合性確認の資料は[gmb_comparison](gmb_comparison/README.md)に保持します。

## solver評価runner

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
