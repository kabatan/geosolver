# 制作経緯（スーパーPC: ~/work/solver 側の記録から）

出典は `~/work/solver` の `git log --all`（1420件）、`~/work/geosolver`、`~/work/solver-experiment/research-archives/`、`~/work/solver-research-assets/`、`~/.codex/sessions/`（Codexの会話記録）です。動機は記録の文言があるものだけ引用し、無いものは「記録なし」としました。

## 先に結論

| 機構 | 現行solverでの初出 | 理由の記録 |
|---|---|---|
| NOMAD主探索、Phase 0/A/B/C、rescue、hybrid fallback、pslq、mpmath_refiner、IsTangent | 2026-07-09の `~/work/geosolver` の時点で既に存在（Initial commit `6e0478a`、2026-07-09）。7/27に `19a6e4e23` で現行系へ取り込み | このPCには無し（下記「見つからなかったもの」） |
| IsTangentの書き換え（同一円の0化、`signed_tangency`） | `faf43a856`（2026-08-30）、`18be44312`（2026-08-31） | commit本文に目的の記述あり（下記） |
| `algebraic_branches`（多項式化→消去→有限候補列挙） | 2026-10-11の最適化作業。`algebra-source`（候補ソース、2026-10-11 14:13）が最古。`baseline-source`には無い | Codexの説明あり（下記） |
| 自由度圧縮（正の拡大縮小の固定、`positive_scale_chart`） | 2026-10-11の最適化作業（`scale-v1-source`、15:06） | Codexの説明あり（下記） |
| 接線の別表現（`tangency_contacts`） | 2026-10-11の最適化作業 | Codexの説明あり（下記） |

## 見つからなかったもの

- `codex/research-before-publish-20261022`、`codex/solver-hardening`、`codex/research-before-import-20260830` のブランチは、このPCのどのリポジトリにもありません。`~/work/solver` のブランチは main、research、experiment のみです（他に `refs/cleanup-20260907/*`、`refs/tags/*`、`refs/codex/turn-diffs`）。
- `~/.codex/sessions/2026/05`、`06` は空で、2026-07-09より前のCodex記録はありません。NOMADをPhase Aの主探索にした経緯、Phase A/B/Cの設計意図は、この時点より前のため記録がありません。
- 7/9の `~/work/geosolver` は、ファイルの更新時刻が2026-04-04のものを含み、Initial commitは2026-07-09に私(利用者)が作ったものです（Codex記録 `~/.codex/sessions/2026/07/09/rollout-2026-07-09T00-21-41-019f4252-...jsonl`）。以前の履歴はありません。
- 旧リポジトリ（NOMAD採用の根拠文書 `EXPERIMENT_PLAN_EXTERNAL_LIB_PILOT.md`、コミット `a238648`/`c62e309`/`47d4b2a`）は、このPCのgit、ファイル検索、Codex記録のいずれにも無し。

## 時系列

| 日付 | 出典 | 内容 |
|---|---|---|
| 2026-07-09 | `~/work/geosolver/docs/SOLVER_REFACTORING.md`、`docs/reports/OPTIMIZATION_REPORT.md`（Initial commit `6e0478a`） | 既存の設計として「Phase 0: cheap random probe + structure-aware manifold sampling → Phase A: global/candidate-search portfolio → Phase B: high-precision refinement or box solver → Phase C: acceptance, de-duplication, answer assembly → Completion strategies: coverage rescue + finite discrete target enumeration」と記載。`pyproject.toml` ではPyNomadは任意依存(`nomad` extra)。PyNomad無しのときSciPy multistartへ戻す処理、`MpmathRefiner` が既に精度基準を満たす候補ではLMを省く処理を同日に追加。 |
| 2026-07-09 | Codex記録 `2026-07-09T00-21-41`（ユーザー発言） | 「PyNomadって導入しました？…このrepoに必要そうなら入れておいてほしい」。計画では「Existing external pipeline already has Phase0/PhaseA/PhaseB/PhaseC boundaries and should be extended, not replaced」。同日Julia kernel案(`docs/JULIA_KERNEL.md`)は無効の雛形のみ。 |
| 2026-07-10〜12 | `474915315`〜 | clean-slate再開。7/12に代替の局所最適化(Powell hybrid `cfffdef7c`、DFO-LS `b6e5cec97`、OrthoMADS `77effffc9`)を比較して不採用。これはGeoTarget系の実験で、現行solverの採用根拠としては別扱い。 |
| 2026-07-12 | `c157254af` | 「feat(exact): add owned PSLQ recognition」(Julia側の別実装、GeoTarget系)。現行Pythonの `pslq.py` は7/9の `~/work/geosolver/src/geosolver/_internal/solver/exact/pslq.py` に既存。 |
| 2026-07-27 | `05439a7b0`、`19a6e4e23` | `champion_v2_poc_preloaded`(開発145問で131/145、extra 0)を凍結し、その実装(`baseline_search_policy.py` の `SEARCH_ATTEMPT_PRIMARY`→`SEARCH_ATTEMPT_HYBRID_FALLBACK`、`hybrid_legacy_nomad`、`run_rescue_search`)を `src/geotarget/_engine/runtime/geosolver/` に取り込み。出典: `research/experiments/EXP-V15-243-001/repro_20260722/FINAL_COMPARISON.md`、`CANDIDATE_TOURNAMENT_20260722.md`。 |
| 2026-08-05 | `807ff9195`、`edb6ab7f0` | 「benchmark failed cases after mpmath refiner fix」「certify high-precision geometry closure」。 |
| 2026-08-22〜24 | `6e15a9d63`、`a5045c6d0` | 「align main solver with experiment runtime」→パッケージ名を `geosolver` へ統一。 |
| 2026-08-26 | `7b2ebf122` | 「fix: restore NOMAD backend and high-precision polar」(`nomad_backend.py`、`run_rescue_search.py`、`uv.lock`)。理由の本文なし。 |
| 2026-08-30 | `faf43a856` | 「replace legacy solver with cleaned pipeline and 323-case corpus」。IsTangentに「`d == 0 and r1 == r2` なら `r1 + r2` を返す」(同一円を0残差にしない)を追加。 |
| 2026-08-30 | `~/work/solver-research-assets/workspace-before-research-root-20260830/snapshot/SOLVER_PIPELINE_CLEANUP.md` | 「探索順、候補配分、時間配分…は変更していない」「NOMAD、SciPy fallback/hybrid、救済探索、整数補完の有限cap」「180秒・1 core」を維持と明記。 |
| 2026-08-31 | `18be44312` | `signed_tangency.py` 追加。docstring: 「Have the same absolute value/domain as IsTangent, without its zero cusp. …Unlike a squared residual, its units and conditioning remain those of the public distance residual.」局所微分用の内部関数で、公開DSL記号ではない。 |
| 2026-10-11 | Codex記録 `~/.codex/sessions/2026/10/11/rollout-2026-10-11T13-53-00-01a1294e-9ce1-77b3-92fd-22d6a4b15ec9.jsonl` | 利用者の依頼(JST 14:04頃): 「solverの性能改善を限界まで…成功率99%, 実行時間の中央値1秒未満」「テストケースに過適合した改善はやめてください」。契約は「1問題180秒・1コア、厳密値descriptor、最終検証の強さを維持」(利用者が確認)。以後 `optimization-20261011` に候補ソース約80本。 |
| 2026-10-11 | 同上 final_answer（08:15Z） | 下の「10/11の改善」参照。 |
| 2026-10-11 | `optimization-20261011/adoption-receipt.json` | 採用は `candidate-v8-source`(ソースhash `f92ee9ba…`)。不採用: 整数セグメント近道、正半径contact sampler、角度の整数倍拡張、ledger interval cache、literal cache、解析微分の拡張、deadline-list微最適化。 |
| 2026-10-21/22 | `052a4771f`、`1aa9139d4` | 研究ツリーを `research-archives/2026-10-21/` へ退避し、`algebraic_branches.py` 等をresearchに公開。 |

## 10/11の改善（Codexの説明そのまま要約、出典は上のrollout）

1. `gmpy2/GMP` による高精度計算の高速化(桁数は維持)。
2. 解析微分とNewton法で答え付近の反復を削減。
3. 二進表現まで同一の座標の高精度検証を再利用。
4. **`algebraic_branches`**: 「対応できる幾何条件を多項式に変換し、変数を消去して、有限個の実数解の候補を求めます」。動機: 「数値探索が片方の解にばかり集まる問題を減らします」。式変形で増えた根は元の条件で検査し、未確認の枝が残れば通常探索も実行。
5. **接線の別表現**: 点Pが円上と確認できれば接線条件を `(P-O)·d=0` で表す。動機: 「接する位置の近くで変化が小さくなる距離式より、補正方向を求めやすい場合がある」。元の条件も保持して検査。
6. **自由度圧縮**: 「図形を一様に拡大しても条件と答えが変わらないと式から確認できる場合は、正の変数を一つ1に固定した代表配置でも候補を探します。大きさの自由度を減らせるためです。」実装は `problem/positive_scale_chart.py`(冒頭: 全変数のt>0倍で、構成が同変、等式・不等式が斉次、答えが次数0であることを証明して固定)と `search/scale_chart.py`。
7. 結果(同seed): 中央値6.183→2.997秒、完全一致309→321問(323問、seed 0)。「個々の改善の寄与を全問題で完全に分離した数値ではない」「36問の速度悪化も残っている」。出典: `research-archives/solver-evidence/optimization-20261011/final-report.json`。

候補の段階(ファイル構成から確認できる範囲): `baseline-source`(algebraic_branchesなし) → `algebra-source`〜`algebra-v11-source`(algebraic_branches、v9で `algebraic_branch_boxes.py` 追加) → `scale-v1/v2`、`analytic-*`、`candidate-v1`〜`v8`。各候補の細かな差分と採否理由の本文は未精査です。

## 未確認

- 「Hybrid DE」「第2探索」を導入した日付と理由(7/9より前)。
- IsTangentの7/9以前の版。
- `candidate-v1`〜`v8` ごとの差分と測定表(`candidate-vN-development`、`candidate-vN-partial-comparison.json` に素材あり)。
