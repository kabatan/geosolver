# researchから移管したGeoSolver実験記録

2026-09-08に、`research` の過去実験記録を既存の `experiment` ブランチへ移管しました。移管前のsource commitは `8c1b974e3`。このブランチの既存GeoTargetコードは当該GeoSolver測定に使ったコードではありません。

## Gitに保存した記録

元の相対パスを `snapshot/` 以下に保持し、52ファイルのバイト列を照合しています。

- [solver改善の報告](snapshot/benchmarks/solver-improvement-report-20260907.md)、[事前規則](snapshot/benchmarks/solver-improvement-protocol.md)、[集計](snapshot/benchmarks/solver-improvement-results-20260907/summary.json)
- [GMB公開問題の計測](snapshot/benchmarks/gmb/results/)
- [GeoSolverとGMBの比較結果](snapshot/benchmarks/gmb_comparison/results/)
- [2026-09-07の整理記録](snapshot/docs/research/cleanup-2026-09-07.md)と[2026-09-08の圧縮記録](snapshot/docs/research/cleanup-2026-09-08.md)

[manifest.json](manifest.json) に元のパス、archive内のパス、SHA256、サイズを保存しています。履歴を書き換えず、既存 `experiment` の後ろに追加しました。

## ローカル生データ

対応するGMB campaign、solver改善campaign、整理時の退避資料を、同じworktreeの `local/benchmarks/local-evaluation/` へ移動しました。元と先の全ファイルhash・symlink文字列を照合しています。[local-manifest.json](local-manifest.json) が移管一覧です。

**`local/` はGit対象外です。** 以前からGit対象外だった生データをこのworktreeへ移したもので、cloneやbranch checkoutだけでは復元されません。保存場所は `/home/kabatan/work/solver-experiment/research-archives/2026-09-08/local/`。5GBを超えるrawをGit履歴へ追加してはいません。

各campaign内のmanifestに書かれた旧絶対パスや測定時刻は書き換えていません。snapshotの文書にある `benchmarks/local-evaluation/` は移管前の場所で、現在は本archiveの `local/` 以下に対応します。ファイルごとのhash一覧は `local/inventories/` にあります。

## 閲覧・再現

`research` checkoutからもGitに保存した報告を読めます。

```bash
git show experiment:research-archives/2026-09-08/snapshot/benchmarks/solver-improvement-report-20260907.md
```

過去のrunner・原典・入力を同じ配置で必要とする場合は、移管前commitを別checkoutへ取り出します。測定コードの正確な版は各campaignのsource manifestとcode snapshotで確認してください。

```bash
git worktree add --detach /tmp/geosolver-experiment-replay 8c1b974e3
```

必要なlocal campaignをそのcheckoutの `benchmarks/local-evaluation/` にコピーし、圧縮runは該当 `archived-runs/<campaign>.tar.gz` を展開します。既存のrawや測定結果を上書きせず、新しい再実行は別出力先へ保存してください。

現在のベンチマーク入力・数値参照・存在証拠・source review、および再利用するrunnerは `research` にあります。本移管は新しい性能測定や、以前の実験結論の変更ではありません。
