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
- `benchmark_results_180s_1core_latest_full_2026-08-22.json`: strict guard、exactification factor、rank-aware closure、affine π exactificationを結合した最新runtimeで、全302件をseed 7・180秒・1 coreにより連続再測定したraw結果。
- `benchmark_results_180s_1core_latest_full_strict_2026-08-22.json` / `BENCHMARK_REPORT_180S_1CORE_LATEST_FULL_2026-08-22.md`: 上記full runをraw厳密解集合で再採点した成果物と報告。verified 205件中190件が厳密集合一致（92.68%）。
- `exact_truth.jsonl`: 各DSLの`answer`式に対する、問題文を手作業で確認したraw厳密解集合。`published_answer`（AIMEの`a+b`等）はpresentation referenceとして別保持します。
- `benchmark_results_180s_1core_strict_raw.json`: 上記180秒測定をraw厳密解集合で再採点した結果。`post_process`や代表解の最終形式変換は採点に使いません。
- `BENCHMARK_REPORT_180S_1CORE_STRICT_RAW.md`: raw厳密解集合一致を正答とした採点定義、分母、内訳、再現検査の報告。
- `FAILURE_CASE_AUDIT_STRICT_RAW.md` / `FAILURE_CASE_AUDIT_STRICT_RAW.jsonl`: strict failure 66件をcase単位で、raw Phase C値、DSL constraints/guards、source hash、runtime証拠と突合した原因監査。
- `build_failure_case_audit.py`: 上記failure auditをbenchmark/truth/manual DSLから再生成し、66件のcoverageを検査するスクリプト。
- `FAILURE_CASE_INDEPENDENT_CHECKS.json` / `verify_failure_case_independent.py`: solver本体を呼ばずに、no_solutionの独立 witness、DSL代数矛盾、`Area`のunsigned semanticsを再現する検算。
- `exact_scoring.py` / `rescore_strict_benchmark.py`: 記号式の双方向集合比較と既存測定結果の再採点ツール。小数単独は厳密解と認めず、同じ記号解に付随する小数シリアライズだけを重複として除外します。再採点は固定runtimeのSymPyで実行します。
- `build_exact_truth.py`: source statementとraw解答台帳を生成する監査スクリプト。
- `BENCHMARK_REPORT_180S_1CORE.md`: 180秒/1 core測定の条件・集計・検証結果。
- `BENCHMARK_REPORT_180S_1CORE_FINAL.md`: 最終DSLの180秒/1 core集計と、不一致をDSL/solver数値/採点器に分離した報告。
- `BENCHMARK_REPORT_180S_1CORE_AFTER_GENERAL_FIX.md`: 個別DSL回避策を戻し、共通API境界を修正した後の集計・回帰検証。
- `DSL_REPAIR_BENCHMARK_REPORT_180S_1CORE.md` / `benchmark_results_180s_1core_dsl_repairs.json`: DSL不備を修正した10ケースだけの180秒・1 core再実行結果。strict exactは6/10で、残る不一致は境界・近退化のsolver数値偽陽性として独立監査しています。
- `DSL_DEFICIENCY_REPAIR_REPORT.md` / `benchmark_results_180s_1core_remaining_dsl_fixes.json`: 残り35件の監査で確認した3件（HMMT-2007/2013/2021）のDSL定義修正、意味保存の証拠、180秒・1 core再実行結果。
- `DSL_DEFICIENCY_AUDIT_2026-08-05.md` / `benchmark_results_180s_1core_dsl_deficiency_repairs_2026-08-05*.json`: 全DSL再監査で見つけた内部符号・線分順序・凸順序・未使用自由変数の修正（22ファイル）と、修正ケースの180秒・1 core再実行結果。
- `BENCHMARK_REPORT_180S_1CORE_FAILED35_AFTER_DSL_FIXES.md` / `benchmark_results_180s_1core_failed35_after_dsl_fixes.json`: 前回strict failureだった35件を、修正後DSLでseed=7・180秒・1 coreにより再測定した結果（厳密解集合一致1/35）。
- `validate_dsl_repairs.py`: 上記10ケースだけを実行したこと、`budget=180`、affinity `[0]`、strict集合フラグを機械検証します。
- `runtime_api_compat_regression.py`: 公開DSLの`Line`/`Rotate`/`Tangent`/`IncircleContactPoint`/`Perimeter`と数式caretを一括検査する回帰テスト。
- `runtime_general_fix_manifest.json`: 外部runtimeの修正対象ファイルとSHA256、再現用回帰テストの固定マニフェスト。
- `STRICT_GUARD_FIX_REPORT_2026-08-05.md` / `benchmark_results_180s_1core_strict_guard_fix_v2_2026-08-05.json`: strict inequality・非退化境界の偽陽性をsolver側で修正し、対象12件を180秒・1 coreで再測定した報告とraw結果。
- `runtime_strict_guard_fix_manifest.json`: strict guard修正版の外部runtimeファイルSHA256と再現条件。元のfrozen runtimeは変更していない。
- `verify_strict_guard_fix.py` / `runtime_strict_guard_fix.patch`: strict margin受理の最小回帰検証と、修正版runtimeの再適用用diff。
- `EXACTIFICATION_FACTOR_FIX_REPORT_2026-08-12.md`: PSLQの重複・可約関係が残差を人工的に縮小して通過するexactification検証器バグの一般修正報告。
- `runtime_exactification_factor_fix_manifest.json` / `runtime_exactification_factor_fix.patch` / `verify_exactification_factor_fix.py`: 因数分解・根距離検証の固定SHA256、再適用diff、72近傍の誤受理回帰検証。修正版runtimeはstrict guard測定runtimeと分離している。
- `RANK_AWARE_CLOSURE_FIX_REPORT_2026-08-12.md` / `runtime_rank_aware_closure_fix_manifest.json` / `runtime_rank_aware_closure_fix.patch`: underdetermined・構造的rank欠損系を局所full-rank chartで高精度化する一般修正、全source残差による再認証、対象6件+対照1件の180秒/1 core厳密集合一致を固定する。
- `AFFINE_PI_EXACTIFICATION_FIX_REPORT_2026-08-12.md` / `runtime_affine_pi_exactification_fix_manifest.json` / `runtime_affine_pi_exactification_fix.patch`: 実代数的数`A,B`を持つ`A*pi+B`の有界PSLQ復元、式全体の直接距離検証、π対象3件の180秒/1 core厳密集合一致を固定する。
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

## 正誤判定の定義

solverの正答は、contestの最終入力形式ではなく、DSLの`answer`式が取り得る数学的な厳密解集合とPhase Cの`answer_values`集合が一致することです。例えば本文が「量が`a/b`と表されるので`a+b`を答えよ」と言う場合、truthには`a/b`を登録し、`a+b`は`presentation_answer`にだけ残します。DSL JSONからは`post_process`メンバーを全て削除しました。

比較はSymPyの記号式を簡約したうえで双方向に行い、数値許容幅で別解を同一視しません。Phase Cが同一根について出す小数fallbackは、同じ記号式が併記されている場合に限りシリアライズ重複として捨てます。記号式のない小数だけの出力は、厳密解集合一致とは判定しません。truthが独立に確定していない行は`truth_status=unresolved`として、正答率の分母から隠さず別集計します。

`decimal-only` は、Phase Cの`answer_values`に記号的な厳密式がなく、候補の高精度数値文字列だけが出力される状態です。`run_phasec_assembly.py`は`identify_answer`が厳密式を返せないときに`str(candidate.answer_hp)`へfallbackします。この値は近いことの診断には使えますが、例えば正答`408`に対する`407.999999…`のような出力も、厳密解集合としては`408`と同一視しません。記号式と同じ根の小数が併記された場合だけ、シリアライズ重複として除去します。

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
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python run_benchmark_parallel.py \
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
