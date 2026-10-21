# GeoSolverの評価・機構分析資料

ローカルに残っていた資料から、報告書・集計・正解の導出・再現コード・採否の根拠をGitで取得できる形に整理しました。
solverの実行や性能の再測定は行っていません。

| 資料 | 入口 | 対象 |
|---|---|---|
| 2026-10-11の採用済み改善 | [最終報告](optimization-20261011/final-report.json)、[323問の比較](optimization-20261011/final-paired-seed0.csv)、[過適合監査](optimization-20261011/overfit-audit-receipt.json) | 当時の採用版 |
| 同日の追加高速化・不採用理由 | [最終報告](optimization-speed-20261011/final-report.json)、[記録の読み方](optimization-speed-20261011/README.md) | ソースhash `f92ee9ba…`を基準にした試作版 |
| 追加評価用の生成88入力 | [元の凍結記録](optimization-speed-20261011/fresh-holdout/manifest.json)、[生成コード](optimization-speed-20261011/generate_fresh_holdout.py) | 11構造族、4パラメータ、2等価表現。求解未実施との当時の記録 |
| 9月のsolver機構分析 | [資料の読み方](solver-analysis/README.md)、[日本語報告書](solver-analysis/report/research-report-ja.md)、[PDF](solver-analysis/report/research-report-ja.pdf) | commit `e703e2d99484793f162f961bc50126ae65e4069f`、ソースhash `6d59d43c…` |

researchでは[生成88入力](https://github.com/kabatan/geosolver/tree/research/benchmarks/generated-88)だけを追加benchmarkとして保持します。
入力のDSL・参照答・導出は変更せず、caseレコードに`problem_kind: generated`を追加しました。既定の自然問題323問とは混ぜません。

## 取得範囲と検証

`import-manifest.json`は、コピーしたファイルごとの元の保存先・サイズ・SHA-256と、公開用に追加した索引のhashを記録します。
標準Pythonだけで、このディレクトリの保存内容を検証できます。solverは起動しません。

```bash
python3 research-archives/solver-evidence/verify.py
```

報告の根拠となる集計・対比較の小さな記録を選び、全worker捕捉データの重複登録は避けています。
大きな生ログ、途中状態、仮想環境、描画の一時ファイルはローカル限定です。既存資料は削除・移動していません。

```text
/home/kabatan/work/solver-experiment/research-archives/solver-analysis/
/home/kabatan/work/solver-experiment/research-archives/2026-10-21/local/original-tree/benchmarks/local-evaluation/optimization-20261011/
/home/kabatan/work/solver-experiment/research-archives/2026-10-21/local/original-tree/benchmarks/local-evaluation/optimization-speed-20261011/
```

cloneで得られるのはこの索引・manifestに列挙した資料です。ローカル限定の完全な生データはcloneに含まれません。
記録内の絶対パス・commit・時刻・hashは当時の値をそのまま保持しています。再実行には保存されたソースと依存lockを使い、入出力先を現在の場所に設定し直してください。
歴史的な性能値を現在のresearch実装の成績として扱いません。
