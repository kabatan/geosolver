# Windows PC の証跡の総ざらい（制作経緯・設計判断）

調べた場所: R1（`C:\Users\bakat\OneDrive\ドキュメント\geosolver`、147ブランチ、2025-12〜2026-04、docs 176本）のgit履歴とdocs、`~/.codex`・`~/.gemini`・`~/.claude`・`~/.cursor`、`ai_agent_failure_audit`、Downloads、OneDrive各フォルダ、WSL `~/work`。読み取りのみで、変更はしていません。

## 結論

- 「NOMADがDEに勝った」という実験記録は、どこにもありません。NOMAD採用は、判断と小さなパイロットに基づくものです。
- 判断の記録は2026-03-02のCodexセッションと、R1のコミット 13c1b57 / a238648 にあります。
- rescueを入れた理由は、2026-03-04のCodexセッションと a238648 の `SIMPLE_EXTERNAL_SOLVER_INTEGRATION_PLAN.md` に、数値付きで残っています。
- 2025-12〜2026-01は、gitに DE（`scipy.differential_evolution`）だけがあり、NOMADもrescueも出てきません。コミットメッセージにも理由は書かれていません。
- 計測として残っているのは、2026-10の ablation（NO_NOMAD、NO_RESCUE など）だけです。

## 一覧（場所・中身・3章で使えるか）

| # | 場所 | 中身（要約） | 3章で使えるか |
|---|---|---|---|
| 1 | `~/.codex/sessions/2026/03/02/rollout-2026-03-02T20-12-10-019cae3f-9de4-79c1-a1f2-2592c8d88404.jsonl`（305, 326, 443, 498, 546行目） | 外部ライブラリ導入の計画レビュー。レビュアーは「DEが先、NOMADはC++ビルドが重い」と主張。結論は「NOMADを前段の必須とし、Julia案は退け、後段はmpmathに統一」。 | 使える（理由と日付）。実験比較としては書かない。 |
| 2 | R1 `13c1b57:docs/EXPERIMENT_PLAN_EXTERNAL_LIB_PILOT.md` §1.2〜1.3 | 「`OMCE017(F)` は hidden constraints / 不連続性が強く、単純な DE は不利」。DEは主経路に採用しない。 | 使える。`r1-design-rationale.md` に原文あり。 |
| 3 | R1 `a238648:benchmarks/logs/external_lib_pilot_phase0_metrics.json` | ランダム10000点での測定。omce017f は評価失敗0.5519、guard通過0.1922。omc008e は評価失敗0。 | 使える（hidden constraintの実測）。DEとの比較ではない。 |
| 4 | R1 `a238648:docs/SIMPLE_EXTERNAL_SOLVER_INTEGRATION_PLAN.md` §2.7、§5.2.2、§5.6 | rescueの動機。OMCE019F の Phase A 1000点のうち guard を満たす379点に真値に近い候補があったが、上位保持で落ちた。真値との差は 0.1785 → 保持を広げて multi-box rescue で 0.0344。起動は条件付き。 | 使える（最も強い）。「これはまだ完答ではない」と文書自身が書いている。 |
| 5 | `~/.codex/sessions/2026/03/04/rollout-2026-03-04T21-35-02-019cb8d8-3239-7cd0-b52c-1617228dea39.jsonl`（794, 1058, 1410, 1607, 2167行目） | 「正しい枝はPhase Aの全記録にあるが dedup20 で落ちる。探索不足ではなく保持戦略の欠陥」。box内で再探索すると誤差0.0176。 | 使える（rescueの動機）。 |
| 6 | R1 コミット 47d4b2a、db54a09、6edf753、dc45e09、5fb4ed3 の本文 | hybridを既定にした理由とfarthest-point開始点の理由。UQ10_P4 と seed 99 が例。 | 使える（「失敗Xがあったので機構を足した」）。前後の正解数は無し。 |
| 7 | R1 `a225038`、`c3ff8ad`、`c628d74`（experiment/solver-generalization） | LM主＋DEフォールバック（標準ケース58〜80%）、scipyマルチスタート。DEは分岐の不連続へのフォールバックとして使われた。 | 条件付き（別系統の実験）。 |
| 8 | `~/.codex/sessions/2026/03/10/rollout-2026-03-10T02-24-21-019cd3a0-e0b4-7b52-a46f-a1dcb34333f3.jsonl`（6, 326行目） | 10人のAIの計画の再現結果。reduced-gradient 8/8、LM主＋DE 4/4、nullspace-Newton 7/7（180秒超）。 | 使える（捨てた方法と代替案）。 |
| 9 | `~/work/jssa-data/ablation-NO_NOMAD-per-run.csv`、`ablation-NO_RESCUE-per-run.csv` ほか | 2026-10 の ablation。NOMAD無しで時間の中央値が5.3→29.0秒。2番目の探索を外すと317→308問。rescue等は1 seedでは差が小さい。 | 使える（唯一の計測。rescueは効果が見えないと正直に書く）。 |
| 10 | `C:\Users\bakat\OneDrive\ドキュメント\geosolver\docs\geosolver-algorithm-spec.md`（2026-04-15） | 設計の事後説明。「Phase Aは広く浅く、rescueは狭く深く」。feasibility-firstの理由。 | 使える（設計の言い方）。DE対NOMADは無い。 |
| 11 | 同 `docs\plans\2026-04-08-multi-branch-solver.md` | 失敗した枝のrescue上限（既定3）の計画。 | rescueの発展として使える。 |
| 12 | `C:\Users\bakat\ai_agent_failure_audit\geosolver_failure_root_causes.md` ほか | OMCE017Fの枝の欠落を個別に直していた、という批判的な整理。 | 限界の節で使える。 |
| 13 | R1 の docs 一覧（176本、大半は `80de696` 以前に存在し、`ca8f043` で削除） | `git show 80de696:docs/<file>` で読める。 | 個別に引用できる。 |
| 14 | `jssa-notes/chatgpt/consult-04.md`、`consult-05.md` | NOMADは適応的な探索なので、独立開始点モデルは近似にすぎない。 | 5章の注意書きに使える。 |

## 見つからなかったもの

- NOMADとDEを同じ問題で比べた表。
- rescue導入の前後での正解数を示す数値。
- 2025-12〜2026-01のコミットメッセージに、設計理由が書かれたもの。
- Gemini・Cursor・Claudeの記録に、設計期のNOMAD議論は見つかりませんでした。
- Codexの `memories`・`history.jsonl` にも、NOMADの議論はありません。
- 次の文書は、Codexの記録から参照されていますが、作業ツリーにはありません（gitの過去commitか、zipのpackの中の可能性があります）。
  - `REMEDIATION_PLAN_V9.md`
  - `GLOBAL_OPTIMIZATION_BRANCH_RECOVERY_PLAN.md`
  - `agent_experiment_summaries/`
- 未調査: `geosolver.7z`、`geosolver-src.zip`、`kaggle`・`wt-w1` フォルダ、4月以降のCodexセッション。

## 注意

- R1 には `origin/experiment` がありません。実験系のブランチ（`experiment/solver-generalization`、`copilot/evidence-experiments`、`copilot/optimizer-reduced-gradient-experiment`、`codex/generic-optimizer-experiment`）は、すべて `research` から到達できます。
- WSL の `~/work/geosolver`（373コミット、2026-07-10開始）は、書き直した履歴です。12月〜3月の日付の証拠には使えません。
