# GeoSolver改善結果 — 2026-09-07

固定した基準版と最終候補を323問×3 seedで比較し、失敗・タイムアウトを含む全実行時間で採否を判定した。生成問題は調整用4族と未調整4族に事前分割した。公開DSL、solve API、厳密値descriptor、最終検証と`completeness=unknown`を維持する。

基準source: `sha256:4ea84775b41aa64bc9c312245aea8163d39ca94d8e71ed2da568a080ba76213c`。最終source: `sha256:6d59d43c8bcbe882e0cf35457e1671ed7ef94a421b6c67c8c98268308f2fe758`。

## 全323問・3 seed

| seed | 基準完全一致 | 最終完全一致 | 基準総秒 | 最終総秒 | 時間変化 |
|---|---:|---:|---:|---:|---:|
| 0 | 309/323 | 308/323 | 9284.856 | 9224.279 | -0.65% |
| 1 | 312/323 | 312/323 | 9460.280 | 9358.489 | -1.08% |
| 2 | 308/323 | 310/323 | 8951.546 | 8853.164 | -1.10% |
| 全体 | 929/969 | 930/969 | 27696.682 | 27435.932 | -0.94% |

完全一致率の差は+0.103ポイント、全実行時間比は0.990586。入力hash、期待答え、依存lock、180秒・1 core・thread設定の一致を比較器で検査した。採用判定は`numerical_gate_passed=true`。同率同時間だけでは改善と判定しない。

| 指標 | 基準 | 最終 |
|---|---:|---:|
| 部分集合あり | 8 | 8 |
| 余計な答えあり | 0 | 0 |
| 実行エラー | 0 | 0 |
| 答えなし | 32 | 31 |
| 期限終了 | 30 | 34 |
| 総solver時間（秒） | 27539.301 | 27274.167 |
| 総CPU時間（秒） | 24386.060 | 23992.250 |
| 全実行時間中央値（秒） | 7.662 | 7.209 |
| 全実行時間p95（秒） | 173.261 | 174.067 |
| 最大RSS（MiB） | 252.535 | 248.637 |
| 共通正解928実行の総秒 | 21885.112 | 21711.287 |

[全969実行の比較CSV](solver-improvement-results-20260907/cases.csv)には悪化・不正解も含む。段階別時間、CPU、RSS、各counterは[機械可読summary](solver-improvement-results-20260907/summary.json)に保存した。

完全一致の変化：

- 改善: `AIME-2018-II-14` seed 2, `JMO-2025-PRE-05` seed 2
- 悪化: `AIME-2016-I-15` seed 0

## 事前固定した生成問題族

生成seedは20260907。各族6個のパラメータ、原形と同値形の2形式で12実行。等式順の反転、残差の−7倍、冗長な0=0式を組み合わせた。期待答えは生成時に解析的に導出し、workerへ渡さない。

| 分割・族 | 基準正解/12 | 最終正解/12 | 基準秒 | 最終秒 | 両形式正解/6 |
|---|---:|---:|---:|---:|---:|
| 調整・closed_endpoint | 12 | 12 | 21.472 | 14.532 | 6 |
| 調整・polynomial | 0 | 12 | 20.731 | 14.931 | 6 |
| 調整・scaled_linear | 12 | 12 | 64.014 | 61.808 | 6 |
| 調整・tangent_polynomial | 1 | 12 | 151.751 | 20.379 | 6 |
| 未調整・bisector | 12 | 12 | 24.248 | 17.264 | 6 |
| 未調整・circle_line | 4 | 12 | 22.323 | 16.905 | 6 |
| 未調整・reflected_distance | 4 | 12 | 24.218 | 17.726 | 6 |
| 未調整・right_triangle | 12 | 12 | 23.221 | 17.582 | 6 |

未調整48実行は基準32/48→最終48/48、全時間94.010→69.477秒。最終候補を選んだ後に一度だけ評価し、その結果によるパラメータ調整はしていない。[未調整全実行CSV](solver-improvement-results-20260907/holdout-cases.csv)。

## 戦略比較と採否

screenはhash順で固定した開発32問と調整48問、seed 0。同じscreenで順に一戦略ずつ変更し、組合せを単純化して再比較した。screenの速度差だけを最終採用の根拠にはしていない。

| 実験 | 開発/32 | 調整/48 | 全80実行秒 |
|---|---:|---:|---:|
| baseline | 31 | 25 | 1083.319 |
| stage2-v2 | 30 | 24 | 1094.271 |
| stage2-integer-v2 | 30 | 24 | 1063.689 |
| stage3-progressive-v2 | 30 | 24 | 1067.510 |
| stage3-expansion | 30 | 25 | 1075.966 |
| stage4-reuse | 30 | 25 | 1072.848 |
| stage4-sparse | 30 | 25 | 1068.924 |
| stage4-quality | 30 | 25 | 1078.135 |
| stage4-intermediate | 30 | 25 | 1077.078 |
| stage4-trf | 30 | 25 | 1148.669 |
| stage4-guards | 30 | 25 | 1123.660 |
| stage4-rank-first-v2 | 30 | 25 | 1148.475 |
| stage4-preserve | 30 | 25 | 1144.406 |
| stage4-adaptive | 30 | 25 | 1112.047 |
| stage5-local | 30 | 24 | 1084.976 |
| stage5-noadaptive | 30 | 24 | 1081.538 |
| stage5-conservative | 30 | 24 | 1058.377 |
| stage6-scalar-v3 | 30 | 45 | 892.005 |
| stage7-scalar-no-rank | 30 | 45 | 896.979 |
| stage8-scalar-budget | 30 | 48 | 889.368 |
| stage9-noadaptive | 31 | 48 | 876.407 |
| stage10-score | 31 | 48 | 886.295 |
| stage11-norm | 30 | 48 | 896.492 |
| stage12-reserve | 31 | 48 | 904.319 |
| stage13-polygon-cache | 30 | 48 | 916.320 |
| stage14-hp-guard | 31 | 48 | 881.269 |

初期stage1はseed 0の完全一致数が同じで時間+0.87%、stage1→stage2も同数で+1.18%であり、単独では性能基準を通らなかった。最初の最終候補は969実行で929→923件、総時間+2.02%となり不採用。答えの安定性による早期停止と通常域の丸め変更を撤回した第2候補も929→928件、総時間−0.11%で不採用。最終化予約の3秒下限を試した第3候補も929→928件・総時間+0.51%で不採用。予約時間を元に戻し、多角形述語の厳密keyキャッシュと高精度型チェックの負担削減を加えて第4候補を評価した。最終版の主な一般的改善は、一変数で最初の成功だけで止まらず全残差から候補を発見することと、冗長な式でもscalar精密化の反復数を減らさないことにある。多変数の戦略変更は効果が明確なものに絞った。

| レビュー | 最終判断 | 内容・理由 |
|---|---|---|
| F01 | adopted | Recover local Brent deadlines; preserve global TimeoutError |
| F02 | adopted | Memoize shared construction dependencies and maximum literal scale |
| F03 | adopted | Keep rank-chart assembly and typed coordinates at requested precision |
| F04 | adopted | Use exact float tuple seed identity |
| F05 | adopted | Remove fixed-width scalar root merging |
| F06 | adopted | Evaluate closed endpoints and adjacent representable interior points |
| F07 | adopted | Bracket every scalar residual and select distinct local norm minima |
| F08 | adopted | 極端な値だけhypotへ切り替え、通常域の残差ノルムと二乗スコアは従来の計算順・丸めを維持。初期版の一律hypot化でNOMADの探索列が変化したため、有限値の安全性と通常域の再現性を分離。 |
| F09 | adopted | Second-order one-sided finite differences on domain boundaries |
| F10 | adopted | Equilibrate refinement rank tests; explicit verifier error threshold unchanged |
| F11 | adopted | Merge evaluation failure counts using the evaluation population |
| F12 | adopted | 全残差を使う最大2秒のscalar探索を主探索へ接続。候補は通常の精密化と最終検証へ渡す。冗長式でscalar反復数が64へ減らないよう修正。 |
| F13 | not adopted | 推定範囲の拡張はscreenで1件改善したが、同じ取りこぼしをscalar探索で解消。最終版は範囲を変更しない。 |
| F14 | not adopted | 候補の品質重み付けとraw/scaled切替の実験は正答数を増やさず、1078.14秒へ悪化。安定なノルム計算のみF08として残す。 |
| F15 | not adopted | bounded TRFは同じ正答数で1077.08→1148.67秒。元の多変数探索を維持。 |
| F16 | not adopted | A failed evaluator supplies no valid directional residual; replacing it without a domain-specific valid extension would add an unsupported objective. One-sided differences and bounded TRF are tested separately. |
| F17 | not adopted | 品質重み付き選択は同じ正答数で1068.92→1078.14秒。元の選択順を維持。 |
| F18 | not adopted | 候補間の段階的再開は正答数を増やさず、1063.69→1067.51秒。複雑さに見合う効果なし。 |
| F19 | not adopted | 再開スケジューラと一緒に撤回。既存revision・phase history・artifact読取互換性は維持。 |
| F20 | not adopted | Full 969-run evaluation exposed false early stability: 250-digit candidates pass initial verification but fail later 500-digit domain boundary/uncertainty verification. Removing the stop restores five distance-zero failures and a deadline case in the predeclared regression investigation. |
| F21 | not adopted | 局所中断時の追加保持は正答数を増やさず、1078.14→1077.08秒の微差のみ。 |
| F22 | not adopted | 整数部分列挙は正答数を増やさず。最終scalar修正の効果から切り離して撤回。 |
| F23 | not adopted | 最終化予約の3秒下限は第3候補の全969実行で929→928件・総時間+0.51%となり撤回。既存の20%・最大30秒を維持。 |
| F24 | not adopted | 低精度guardの実験は直前のTRF版より速いが、余分な戦略を外した組合せを優先。最終版は元のguard評価を使用。 |
| F25 | partially adopted | 同じ点のJacobianのみ再利用し、点が変われば破棄。rank-firstは2試行0成功で撤回し、元のNewton→rank-chart順序を維持。 |
| F26 | adopted | 残差の静的依存が互いに交わらない列だけ差分を共有。不明な依存は全変数へ保守的に戻す。 |
| F27 | partially adopted | 最終検証の線形代数と閾値は維持。幾何述語だけ、完全な座標表現と計算精度が一致する場合の結果を最大512件再利用。可変Pointのidentityや丸めた値をkeyにしない。 |
| F28 | adopted | factor=1の重複PSLQと同一多項式の重複正規化を除去。探索上限と検証は変更しない。 |
| F29 | partially adopted | snapshot互換性検査は維持。正確なmpf・int型の演算引数だけはfloat混入でないため、高精度モードのcontext参照を省略。floatとsubclassには既存検査を適用。 |
| F30 | not adopted | No profile-backed safe expansion identified; no benchmark-specific limit or expected-answer branching introduced. |
| F31 | not adopted | Profiled serialization under 0.4 percent; preserving partial publication and timeout behavior is more valuable than an unmeasured rewrite. |
| F32 | not adopted | Angle cross product at 1e-200 scale underflows to zero in binary64 although 53-bit mpmath gives pi/2. Numeric probe records counterexample. |
| F33 | not adopted | Isolated 2.2.1 backend speeds numerical microbenchmarks but fails 10 of 165 compatibility regressions, including mpz serialization. Main dependency lock and runtime remain Python backend. |
| F34 | adopted | Retain batch diagnostics and process-wall/p95/execution-layout measurements |

各項目の実験名・元の理由は[review.json](solver-improvement-results-20260907/review.json)に保存した。問題ID・出典・期待答えを使うsolver分岐は追加していない。

## profileと互換性

seed 0でphase時間から事前に選んだ3問を、各30秒の計測予算でprofileした。計測器付き実行は性能集計から除外。3例のelapsedはほぼ同じであり、profileだけから全体高速化は主張しない。厳密値識別数は処理した候補のcounterで、異なる正答の数ではない。早期停止を試した不採用版では、精密化を減らした分が後段の検証へ移り、最終的に答えを返せない例があった。

| 問題（選択phase） | 基準elapsed秒 | 最終elapsed秒 | 基準phase秒 | 最終phase秒 | 厳密値識別数（基準→最終） |
|---|---:|---:|---:|---:|---:|
| HMMT-2006-FEB-GEO-05（refinement） | 23.816 | 23.763 | 21.965 | 21.963 | 5→5 |
| AIME-2014-II-03（exact_assembly） | 28.158 | 28.222 | 19.083 | 20.621 | 7→10 |
| AIME-2021-I-13（search） | 28.090 | 28.109 | 3.008 | 3.020 | 8→10 |

native floatへの単純置換は微小な角度計算のunderflowで意味が変わるため不採用。gmpy2 2.2.1は局所演算を速くしたが、隔離環境の165互換テスト中10件が失敗したため依存に追加しなかった。最終検証・descriptor・不確かさの9ファイルは基準版とhash一致。キャッシュ化した多角形述語と補助関数6個も、関数名を除く構文木が基準版と一致。共有階数判定の明示的誤差閾値経路も変更していない。

## 検証・再現・制約

ローカル全pytestは1331件成功（失敗0、error 0、skip 0）。変更範囲のRuff、schema、compile、build、wheel隔離検証は成功。全体Ruffは861件で失敗し、違反は変更範囲外（着手時の固定treeは867件、共有treeの別作業による増減あり）。CIはlint失敗後もschema・compile・wheel検証を実行するが、lint失敗自体は失敗のまま。詳細はsummary.jsonの`validation`・`ci`を参照。


対応OS CI: [failure](https://github.com/kabatan/geosolver/actions/runs/34132368547)。測定sourceと同じhashの隔離コミットを検証した。既存の155MB benchmark JSONLはGitHubの容量制限によりCI用treeではgzip化し、テスト前に同じデータを復元した。公開済み履歴を親に使用し、ローカルファイル・共有履歴は維持。

| OS | 全pytest | 今回の回帰テスト | compile | schema | wheel | lint |
|---|---|---|---|---|---|---|
| macOS Intel | failure | success | success | success | success | failure |
| Windows | failure | success | success | success | success | failure |
| macOS Apple Silicon | failure | success | success | success | success | failure |
| Linux | success | success | success | success | success | failure |

全pytestには別benchmarkのOS依存も含む。Windowsは`polynomial_comparison/measurement_worker.py`の`resource` importで収集停止、macOSは別benchmarkの`os.sched_getaffinity`使用で失敗した。独立ステップの今回の回帰テスト87件は4環境で成功。CIは着手時treeに今回の変更を重ねた隔離commitなので、共有作業ツリーへ追加された別作業のテストを含むローカル全pytestとは対象数が異なる。

同一環境での再現手順：

```sh
PYTHONPATH=SNAPSHOT/src .venv/bin/python SNAPSHOT/benchmarks/research_runner.py run OUTPUT --jobs 16 --seeds 0,1,2 --allow-dirty
.venv/bin/python benchmarks/research_runner.py assess OUTPUT --cases SNAPSHOT/benchmarks/cases.jsonl
.venv/bin/python benchmarks/research_runner.py summarize OUTPUT
.venv/bin/python benchmarks/compare_solver_campaigns.py BASELINE FINAL REPORT
.venv/bin/python benchmarks/summarize_solver_families.py CAMPAIGN FAMILY_MANIFEST REPORT.json
uv run python -m pytest --import-mode=importlib
uv run ruff check src tests benchmarks .github/scripts
uv run python -m geosolver.schemas.generate --check
uv run python -m compileall -q src tests
uv build
uv run python .github/scripts/verify_wheel.py
```

固定source、入力・依存manifest、生のrun、profile、command/exit記録は`benchmarks/local-evaluation/solver-improvement-20260907/`に保存した（ローカル証跡、Git対象外）。基準実行の中断後は完了済み結果を変えず、未完了case/seedだけを同じ条件で補完し、最初の確定結果をmergeした。一時workerファイルを完了扱いにはしていない。

同時進行の代数benchmark作業があるため、実行は固定snapshotと`--allow-dirty`を用いた開発測定。clean release測定ではない。16物理core、1 job/core、各thread数1、180秒の同一条件でcampaignを順次実行し、重いテスト・profileと重ねなかった。3 seed・各1 campaignでの観測結果であり、任意問題の完全性や速度の保証ではない。既存annotated tag `solver-a1`は変更していない。

詳しい事前規則は[評価protocol](solver-improvement-protocol.md)。


## ローカル生データの圧縮保管（2026-09-08）

過去campaignの `runs/` は、全メンバーのSHA256を照合したうえで `benchmarks/local-evaluation/solver-improvement-20260907/archived-runs/<campaign>.tar.gz` に移しました。元の集計・manifest・コードsnapshotはその場所に保持しています。raw runを読む旧runnerを使う前に該当archiveを復元してください。アーカイブ一覧・復元コマンドは[整理記録](../docs/research/cleanup-2026-09-08.md)を参照してください。測定値や採否は変更していません。
