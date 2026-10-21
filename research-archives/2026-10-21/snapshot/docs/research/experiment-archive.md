# 過去の実験記録

過去のsolver改善実験・GMB計測／比較・整理履歴は、既存の **`experiment` ブランチ** に移管しました。`research` の現行treeには結果を残しません。solver、ベンチマークの入力・参照・原典証拠、再利用するrunnerは引き続きresearchで管理します。

## 閲覧

experiment上の入口は `research-archives/2026-09-08/README.md` です。報告、集計、hash一覧、元commit、ローカル生データの保存先をまとめています。

```bash
git show experiment:research-archives/2026-09-08/README.md
git show experiment:research-archives/2026-09-08/snapshot/benchmarks/solver-improvement-report-20260907.md
```

このPCでは `/home/kabatan/work/solver-experiment` にexperiment専用worktreeがあります。researchのcheckoutを切り替えずに閲覧できます。既存experimentの履歴・コードは変更せず、archiveを追加しました。

## Git対象外の生データ

従来からGit対象外だったcampaign・圧縮run・code snapshotは、次へ移動しています。

```text
/home/kabatan/work/solver-experiment/research-archives/2026-09-08/local/benchmarks/local-evaluation/
```

この生データはbranch checkoutやcloneだけでは復元されません。移管一覧とhashはexperiment側の `local-manifest.json` および `local/inventories/` に保存しています。archive文書内の旧絶対パスは測定時の記録なので書き換えていません。

今後の確定した性能測定結果もexperimentへ保存します。researchの問題ケースを作るための数値参照・存在証拠・検証失敗の記録は、問題の再現に必要なデータとしてresearchに保持します。
