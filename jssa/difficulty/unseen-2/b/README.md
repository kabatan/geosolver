# Q30b — 段階1の成果物

HMMTの未使用17問（Guts 16、Team A 1）を作成・監査し、予測まで固定する。
solver・局所探索・試走は実行していない。このタスクでcommit・pushは行わない。

`prediction.md` と `prediction.lock.json` の作成をもって段階1を終了する。
実行には、ユーザーがこれらをcommit・pushしたことの確認と、別タスクでの明示的な許可が必要。
ファイルが存在すること自体は実行許可ではない。

| ファイル | 内容 |
|---|---|
| [authoring-rules.md](authoring-rules.md) | 今回の作成規則と2段階運用 |
| [problem-list.md](problem-list.md)、[problem-list.csv](problem-list.csv) | 採用問題、幾何量、公式出力、PDFページ、DSL hash |
| [cases.jsonl](cases.jsonl)、[dsl/](dsl/) | runner用の入力と幾何量の参照答 |
| [mapping.json](mapping.json)、[cards/](cards/) | 原文の条件とDSLの対応 |
| [source-evidence/manifest.json](source-evidence/manifest.json) | 保存済み公式PDF34冊のURL・元の取得UTC・SHA-256・照合ページ |
| [AUDIT.md](AUDIT.md)、[audit/](audit/) | PDF画像照合、意味監査、20配置の独立代入、静的検査、重複照合 |
| [selection.csv](selection.csv) | 採否と、前担当から引き継いだ先行候補の分類 |
| [prereg/execution-plan.json](prereg/execution-plan.json) | 未許可の次段階仕様。17問×5 seed、180秒、1コア、並列最大4 |
| [prediction.md](prediction.md)、[prediction.lock.json](prediction.lock.json) | 最終予測と入力・証拠・採点コードの固定 |

一次資料はローカルキャッシュから元PDFと同一バイトで保存した。このタスクでネットワークを利用していない。
各ファイルは5,000,000 bytes未満。PDFを再生成・編集していない。
2021は公式Februaryアーカイブ内のSpring 2021（実施日2021-03-06）。

`audit_substitution.py` は明示的な解析座標を独立の初等幾何評価器へ代入するだけで、
GeoSolverをimportしない。`audit_static.py` は公開DSLの静的検証と既存採点側の参照式処理に限定し、
engine/application/searchのimportを禁止する。探索を伴う監査もGeoSolverのCLI呼出しもない。

`revisions/substitution-first-pass.json` は凸性不合格の補助配置を含む初回検算。
最終合格記録は `audit/substitution.json`。失敗配置を理由としたDSLの緩和・変更はない。
`revisions/resumed-authoring-rules.md` は再開前の規則保存物で、現行規則はルートのauthoring-rules.md。
`fetch_sources.py` は前担当の取得スクリプトの保存物であり、このオフライン作業では使っていない。

指定の `benchmarks/new-2026/authoring-rules.md` は現存せず、読んだとは主張しない。
ユーザーの明示的な訂正と現存new2026の慣例に従い、targetは幾何量そのものにした。
採点は既存research_runnerの完全一致判定を変えず、公式の出力形式との対応を参照資料側で保持する。
