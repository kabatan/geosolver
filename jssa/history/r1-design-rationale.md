# R1（旧リポジトリ kabatan/GeoSolver）の設計理由：原文引用

リポジトリ: `C:\Users\bakat\OneDrive\ドキュメント\geosolver`（origin は https://github.com/kabatan/GeoSolver.git）。`git show <commit>:<path>` で読んだ原文です。作業ツリーはOneDriveのため一部ファイルが読み出せず、`git status` は失敗しますが、履歴と各commitのblobは読めました。引用は原文のままで、「記録なし」は指定のcommitと文書に見つからなかったことを指します。

対象commit: 0284ee2（03-02）、13c1b57（03-02）、a238648（03-05）、c62e309（03-25）、47d4b2a（03-28）。

## 1. NOMADを入れた理由

**出典: 13c1b57 / `docs/EXPERIMENT_PLAN_EXTERNAL_LIB_PILOT.md` §1.2〜1.3**

> `OMCE017(F)` は hidden constraints / 不連続性が強く、単純な DE は不利
> - ケース構造上、この主張はかなり plausibility が高い
> - ただし「NaN 率 80〜95%」「有効領域 0.01〜0.1%」という具体値は、現時点では仮説として扱う

> 本 pilot では、前段探索は **`NOMAD`（DiscoMADS 系）を第一かつ必須候補**とし、後段 refinement は **Python 内で `mpmath` に一本化**します。
> `scipy.optimize.differential_evolution` は本 pilot の主経路には採用しません。

**出典: 13c1b57 / 同 §0**

> 1. 外部の大域探索器で良い basin に入れるか
> 2. basin に入った後、`mpmath` ベースの高精度局所 refinement で十分小さい残差まで落とせるか
> を、**最小実装で判定すること**です。

**出典: 0284ee2 / `docs/deep-research-report (4).md`（調査レポート。冒頭）**

> 本件（「部分的にしか定義されない」「不連続な定義域」「等式制約 \(f(x)=v\)」「非線形・非凸」「小数点以下100桁級」）を**単独で**満たす“万能ライブラリ”は、実用レベルではほぼ存在しません。

> したがって推奨は、「**探索（グローバル・頑健）**」と「**高精度化（局所・検証付き）**」を分離したオフライン・パイプラインです。
> - **探索（不連続・評価失敗に強い）**：NOMAD（DiscoMADS含む）で“定義域の穴（hidden constraints）”や不連続を避けつつ候補点を集める。

**出典: 13c1b57 / `docs/EXTERNAL_LIBRARY_INTEGRATION_EXECUTION_PLAN.md` §2.2（導入に踏み切った直接の理由）**

> 今回、外部ライブラリを用いたパイロットを実施し、以下を確認した。
> - 大域探索に `PyNomadBBO` (`PyNomad`) の `DiscoMADS` を使用
> - 高精度局所 refinement に `mpmath` を使用
> - GeoSolver 本体の `solve()` / `optimize()` は使わず、IR 評価器だけを再利用

> - `OMC008(E)`: 高精度 sanity check 通過、最終残差は `1e-79` オーダー、answer は `26`
> - `OMCE017(F)`: 2 解 `312`, `468` を両方回収、2 解の和 `780` を確認、最終残差は `1e-79` オーダー

> 1. 外部大域探索器により、現行本線が入れていない basin に入れる。
> 2. basin に入った後は、`mpmath` の高精度 refinement で十分な桁まで詰められる。

> したがって、今後の本実装は「現行モノリスの延命」ではなく、「評価器を中核に据えた新パイプラインへの置換」を正式方針とする。

**数値（同commit `benchmarks/logs/external_lib_pilot_summary.md`）**

> - elapsed_seconds: 94.89
> - omc008e_phase0_best_random_residual: 1.2865556594311098
> - omce017f_phase0_best_random_residual: 3.122580320686238
> - omce017f_best_phaseb_residual: 5.3393301668034158355628758500151383084292187251709254572591326653040733278558937e-79
> - omce017f_rounded_answers: [312, 468]

**移行の背景（同 §2.1）**

> `REMEDIATION_PLAN_V3.md` から `REMEDIATION_PLAN_V9.md` までの修正は、既存の `solve()` / `optimize()` 本線を維持したまま、候補選択・高精度化・残差評価の不整合を局所修正する方針が中心だった。
> その結果、精度・時間・候補選択・残差ソースの責務が複数層に分散し、`legacy_optimize_engine.py` / `legacy_solve_engine.py` の肥大化と、ラッパー層の意味論不一致が残った。

## 2. 比較した代替とその数値

- 比較の数値（NOMAD対DEなど）は、指定のcommitと文書に**記録なし**です。
- 代替の検討は定性的な記述だけです。`scipy.optimize.differential_evolution` は、上の引用のとおり「主経路には採用しません」とされ、「別 experiment として切り離します」とあります。
- 計画書は「NaN 率 80〜95%」「有効領域 0.01〜0.1%」を**仮説**とし、Phase 0 で実測するとしています。その実測は `benchmarks/logs/external_lib_pilot_phase0_metrics.json`（13c1b57、a238648 で更新）にあります。このJSONの数値は未読です。
- `scipy.optimize.differential_evolution` の最初の出現は 2768733（2025-12-17 "first commit"）で、以降 d36b63b、ea67271 に残ります。

## 3. mpmath_refiner を入れた理由

**出典: 13c1b57 / `EXPERIMENT_PLAN_EXTERNAL_LIB_PILOT.md` §11.2**

> この Phase では、既存の `solve()` / `optimize()` を使わず、**pilot 用に独立した Newton / LM を書く**。
> 理由:
> - 既存 solver の不整合を避けるため
> - 本 experiment の仮説は「構成が正しければ外部二段構成で解けるか」であり、既存本線の挙動は混ぜないため

**同 §1.1（Julia案を退けた理由）**

> **Julia ブリッジは pilot として過大**
> - 既存の幾何評価器は Python / `mpmath` 前提であり、Julia 側へ同等評価器を移すコストが大きすぎる
> - 後段の高精度局所化は `mpmath` で実施する

`mpmath_refiner` の名前が最初に現れるのは 13c1b57（2026-03-02）です。

## 4. rescue を入れた理由

- `select_rescue_boxes` の初出は a238648（2026-03-05 "after external libs integration"）です。
- 入れた理由を述べた文書は指定のcommitに**記録なし**です。
- 関連する後続commit: 8501bf5（03-23 "fix: clamp rescue box centers to global bounds before box creation"）、2a1c224（03-30 "Transplant rescue-first primary completion"、本文なし）。
- dcfe7da（03-28）の本文に「without loosening acceptance thresholds or changing rescue/refinement logic」とあるのみです。

## 5. hybrid_legacy_nomad を既定にした根拠

**出典: 47d4b2a（2026-03-28）commit message 全文の主要部**

> fix(config): switch default search mode to hybrid_legacy_nomad
> NOMAD alone (5 seeds x 200 evals) provides insufficient search-space coverage for multi-basin problems like UQ10_P4 where the true solution is in a distinct basin from the nearest low-residual region.

> Switch the default global_search_mode from disco_mads to hybrid_legacy_nomad.  In hybrid mode Phase A runs NOMAD first, then supplements with scipy multistart (320 Halton quasi-random starts + LM/TRF optimisation) using the remaining time budget.  This gives two independent coverage mechanisms:
> 1. NOMAD: derivative-free DISCO-MADS exploration from farthest-point start points (the preceding commit).
> 2. Scipy: dense 320-point Halton quasi-random multistart with fast gradient-based convergence — proven to find UQ10_P4 via the legacy solver.

> The change is strictly additive: NOMAD runs with the same config and eval budget as before; scipy uses only residual time.

**直前の db54a09（03-28）の根拠**

> Root cause: select_search_start_points sorted Phase-0 candidates by (guard_ok, residual) and greedily picked the top-N with a tiny dedup threshold (0.01 normalized).  For UQ10_P4, all five NOMAD start points fell into the same low-residual-but-wrong basin, leaving the true solution's basin unexplored across every seed.

- 数値として書かれているのは「5 seeds × 200 evals」「320点のHalton」だけです。既定化の前後での正解数や時間の比較は、このcommitには**記録なし**です。
- `hybrid_legacy_nomad` の初出は e4ba6ad（03-25 "pipeline: merge legacy hybrid phasea"）です。

## 6. Hybrid DE から移行した理由

- 「Hybrid DE」という名前のモードや設定は、`git log -S` では見つかりませんでした（`hybrid_de` はヒットなし）。
- 「DE」に当たる記述は、上の §1 の引用（「単純な DE は不利」）だけです。別の文書に「Hybrid DE」の記述がある可能性はありますが、指定されたcommitの範囲では**記録なし**です。

## 7. c62e309（03-25）"Finalize optimizer V9 evidence package"

`docs/OPTIMIZER_PLAN_V9.md` を読みましたが、NOMAD・hybrid・rescue・DEへの言及はありません。内容は、現行コードでの複数seedの再測定と、遅い問題の時間・予算プロファイルのまとめです。結論の一文は次のとおりです。

> Under the current `IR / harness semantics`, the optimizer regains benchmark truth closure through a decomposed current-code evidence pack: fresh multi-seed reruns on the repaired benchmark regressions (`OMC006B`, `OMC039C`, `OMC072D`), ...

このcommitは「NOMADの採用理由」の出典としては使えません。

## 8. 補足：a238648（03-05）の関連文書

`docs/EXTERNAL_PIPELINE_ARCHITECTURE.md`（41行）は構造の説明で、採用理由は書かれていません。冒頭は次のとおりです。

> `geosolver._internal.pipeline` is the primary path for external-library-based solving.
> The pipeline is split by responsibility and wired through contracts.

## 本人に聞くとよい点

- NOMADとDEの比較実験を、文書とは別に行ったか。
- rescue の導入理由と、Hybrid DE の位置づけ。
