# 競技別幾何コーパス（2006--2025）

`experiment` branchで、AIME、HMMT、JMO予選の20年分（2006--2025、両端を含む）をsolver評価用に分離して管理するディレクトリです。既存の145件のartifactや他Agentの実験ディレクトリには手を入れていません。

## 収録物

- `all_geometry.jsonl`: 抽出した問題の統合台帳。問題文、出典URL、取得元、幾何判定の根拠、scope判定、DSLパスを1行1問題で記録します。
- `aime_geometry.jsonl`: AIME I/IIの幾何候補（2006--2024の公開CSVと2025公開行データ）。
- `hmmt_geometry.jsonl`: HMMT February Geometry Round（2011年は既存のAlg/Calc/Comb Geometry PDFも候補として記録）。
- `jmo_geometry.jsonl`: JMO予選の公式画像/PDFを問題番号単位で記録した56件、MathNet補助本文24件、公式年次リンク20件。canonicalなscope内56件は公式画像50件・公式PDF 6件を目視確認して全文転記しています（補助本文は別source rowとして保持）。
- `scope_inventory.jsonl`: 全source rowの手動scope台帳。unique問題の`in_scope`は296件（AIME 108 / HMMT 132 / JMO 56）。HMMT 2011のtrack再掲は`dedupe_key`で一問にまとめています。
- `AUDIT_MATRIX.md`: 年×contestごとのsource row、scope内外、DSL ready/pendingの一覧。
- `dsl/`: 幾何scope内296 unique問題に対応するsource-faithful JSON（HMMT 2011の再掲・MathNet補助本文の別名6ファイルを含め302ファイル）。現行IRで実行可能なのは279 unique / 285 files、残り17 filesは`reference_only`です。
- `benchmark_results.json`: frozen geosolver runtimeを用いた全302 JSONの性能測定結果（seed=7、予算3秒、8並列）。
- `benchmark_results_180s_1core.json`: 同じ全302 JSONをseed=7、180秒hard timeout、1 core固定で測定したraw結果。
- `benchmark_results_180s_1core_evaluated.json`: 上記にcoverage判定と、余分な候補を拒否する厳密解答集合判定を付加した結果。
- `benchmark_results_180s_1core_final.json`: 最終DSL（AIME-2016-I-15の作図修正を含む）と修正済みanswer projectionで再評価した最終結果。
- `benchmark_results_180s_1core_after_general_fix_final.json`: 公開geometry APIと高精度backendの共通互換修正後に、180秒・1 coreで全302件を再測定した結果。
- `BENCHMARK_REPORT_180S_1CORE.md`: 180秒/1 core測定の条件・集計・検証結果。
- `BENCHMARK_REPORT_180S_1CORE_FINAL.md`: 最終DSLの180秒/1 core集計と、不一致をDSL/solver数値/採点器に分離した報告。
- `BENCHMARK_REPORT_180S_1CORE_AFTER_GENERAL_FIX.md`: 個別DSL回避策を戻し、共通API境界を修正した後の集計・回帰検証。
- `runtime_api_compat_regression.py`: 公開DSLの`Line`/`Rotate`/`Tangent`/`IncircleContactPoint`/`Perimeter`と数式caretを一括検査する回帰テスト。
- `runtime_general_fix_manifest.json`: 外部runtimeの修正対象ファイルとSHA256、再現用回帰テストの固定マニフェスト。
- `DSL_INTEGRITY_AUDIT.md` / `verify_dsl_integrity.py`: 302 JSONの重複キー、IR parser、source provenance、変数上限、benchmark coverageを検査する最終監査。
- `validate_benchmark_180_final.py`: 最終benchmarkのstatus・answer-set・CPU affinity検証。
- `PERFORMANCE_DIAGNOSIS.md`: 旧134/145との比較差、answer projection/DSL分岐、solver exception/timeoutを切り分けた検証報告。
- `DOF_COMPRESSION_AUDIT.md`: 自由度冗長性を修正した内容、意味保存の個別監査、修正後39ケースの180秒/1 core結果。現行DSLは302件すべて0--7変数。
- `dof_measurement_180s_1core.jsonl`: 上記39ケースの修正後raw測定（同一case_idは最後の行が最新）。
- `extract_dataset.py`: 同じ入力から台帳を再生成するスクリプト。
- `run_benchmark.py` / `run_benchmark_parallel.py`: DSLをsolverへ渡し、status・elapsed・accepted answersを記録するスクリプト（後者は独立fresh subprocessを並列化）。
- `validate_dataset.py`: 548 source rows、296 unique geometry scope、302 JSON、現行solver scope 279 unique / reference-only 17、ID重複・source_statement一致・benchmark全件coverage/status/解答照合を検査するスクリプト。
- `source_manifest.json`: 公式アーカイブと再配布データのURL、取得日、ローカル入力のSHA256。

## 抽出とscopeの境界

「幾何」は、円・三角形・四角形・多角形・角・垂線・平行・面積・距離などの語を含む問題を候補化し、HMMT Geometry Roundはラウンド名を根拠に全問を収録しています。候補化の後に、AIME/HMMTは各本文を、JMOは公式画像/PDFの各問題を一問ずつ確認し、finite 2D labeled configuration + scalar target かどうかを `manual_scope_audit.py` で固定します。候補抽出件数、source row数、重複除去後のscope件数は別物です。

JMO 2006--2023の公式ページは画像のみの年があります。scope内56件は問題番号を確定したうえで、50件を公式画像から手作業で文字起こしし、6件を公式PDFから転記しています。MathNetの補助本文11件は公式問題番号との対応を別source rowとして保持し、canonical DSLの出典文を置き換えるためには使っていません。図だけで境界や点順を確定できないものは、文字起こし後もJSONの `solver_coverage=reference_only_figure_clause` として未実行に分離しています。

DSL化では、定理による短縮（角の二等分線定理、方べき、Ptolemy等）を使わず、原文の作図・距離・角・内外・順序をそのまま construction/constraints/guards に写します。新しいケースは既存145件のtruthを参照せず、手作業で確認したsource本文とclause ledgerだけから作成しています。各JSONの `source_statement` は監査台帳と完全一致することをvalidatorで確認しています。`extraction_summary.json` の `scope_count`（幾何監査296）、`current_solver_scope_unique`（279）、JSONファイル数（302）、現行IRの実行可能数（285 files）、`reference_only`（17 files）は別フィールドです。

座標圧縮後の変数数については、`DOF_COMPRESSION_AUDIT.md` を正とします。`benchmark_results_180s_1core*.json` と `BENCHMARK_REPORT_180S_1CORE.md` は圧縮前の302件baselineを保存したartifactであり、圧縮後の比較対象は `dof_measurement_180s_1core.jsonl` です。

## 再生成

依存を増やさないため、抽出器は標準Pythonだけで動きます。入力キャッシュを用意した上で、例えば次を実行します。

```bash
python3 extract_dataset.py \
  --aime-csv /tmp/aime.csv \
  --aime-2025-json /tmp/aime_2025.json \
  --hmmt-dir /tmp/hmmt_pdf \
  --jmo-rows /tmp/jmo_mathnet_geometry.jsonl \
  --output .
```

solver評価は、固定runtimeを汚さないよう外部worktreeから実行します。

```bash
python3 run_benchmark_parallel.py \
  --runtime-root /home/kabatan/work/solver-experiment-runtime \
  --seeds 7 --budget 3 --jobs 8 \
  --output benchmark_results.json
```

## 出典

- HMMT公式問題アーカイブ: <https://beta.hmmt.org/www/archive/problems>
- JMO公式概要・年度リンク: <https://www.imojp.org/domestic/jmo_overview.html>
- AIME 1983--2024再配布CSV（元データURLは`source_manifest.json`）
- AIME 2025公開行データ（元データURLは`source_manifest.json`）
- MathNet-filteredの問題本文補助（元データURLは`source_manifest.json`）
