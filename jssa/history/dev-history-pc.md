# GeoSolver 開発履歴（このPC上のgit記録から再構成）

作成日: 2026-10-22。git・ファイルに記録された事実だけを書く。日付は `git log --date=iso` の author date（+0900、1件のみ+0000）。
commitは短縮hash。表記「R1@a238648」は「リポジトリR1のcommit a238648」を意味する。
全commitの生ログはPC上（作業用一時フォルダ）に保存し、ここには載せていない。

## 1. 出典リポジトリ一覧

| 記号 | パス | origin | 期間（全ref） | commit数 | ブランチ |
|---|---|---|---|---|---|
| R1 | `C:\Users\bakat\OneDrive\ドキュメント\geosolver` | kabatan/GeoSolver | 2025-12-17〜2026-04-15 | 1099 | ローカル約147（`candidate/*` 31、`copilot/*` 25、`fix/*` 13、`codex/*` 3、`aimo3-*` 等）。`main`の先端は ec1927d（2026-01-22）で、以降の作業は他ブランチ上 |
| R2 | `C:\Users\bakat\OneDrive\ドキュメント\geosolver-core` | kabatan/geosolver-core | 2026-07-04〜07-05 | 111 | `main`、`codex/archive-p6-p9-before-p5-reset-20260704`。Rust（Cargo, crates/） |
| R0 | `C:\Users\bakat\OneDrive\ドキュメント\bakaGeometry` | kabatan/bakaGeometry | 2026-07-05〜07-09 | 47 | `main`、`legacy-main`。Rust（Cargo, src/*.rs 51件） |
| R3 | `C:\geosolver` | kabatan/geosolver | 2026-07-10〜2026-10-22 | 789 | `research`(60db4b6)、`origin/main`(8ea1e13, 2026-08-24)、`origin/experiment`(7b6691b)、`origin/claude/project-thread-*`、tag `solver-a0`(9d2d328) |
| R4 | `C:\geosolver-previous-local-copy` | kabatan/geosolver | 2026-04-25〜2026-10-22 | 841 | `research`(=60db4b6、R3と同一)、`master`(6732f3f, 05-01)、`theorem-core-cleanroom`(6b1c4f9, 05-14)、`theorem-core-parallel-baseline-runner`(666df4c, 05-12)、`origin/migration/local-master-wip-20260514`(1c5c37c) |

R4について: 単なるR3の複製ではない。`research` はR3と同じ（60db4b6、373 commit）だが、R3に存在しない別系統468 commit（root e55fb83 2026-04-25 "docs: add geosolver research design"〜2026-05-14）を持つ。R4@6732f3f・6b1c4f9・666df4c・1c5c37c はR3にobjectが無い。
WSL（Ubuntu）`~/work/` には geosolver 系の clone/worktree が10個あるが、いずれも origin=kabatan/geosolver で、作成日時は2026-10-22。`~/work/solver`・`~/work/solver-experiment`・`~/work/solver-artifacts` は存在しない。

## 2. 時系列（フェーズごと）

### フェーズA: R1 初期（2025-12-17〜2026-01-31）
- R1@2768733 2025-12-17 "first commit": README に「Rust版（geosolver-rs）で近似値、Python版PSLQで厳密値」と記載。`algebraic.py`（mpmath.pslq 使用）、`geometry/compat/geogebra.py`（`IsTangent(line, circle, tolerance=1e-12)`）を含む。
- R1@7c22f17 2026-01-19 "かなり大規模な変更": `src/geosolver/solver/optimize_impl.py` に「Hybrid DE探索」。
- R1@269a1f8 2026-01-28: `src/geosolver/geometry/operations/basic.py` に `IsTangent(obj1, obj2)`、`mp_api.py` に `MP_IsTangent` を追加。
- 1月の commit 数 13。

### フェーズB: R1 タスク分割による大改修（2026-02〜03-01、451+ commit）
- R1@d3aa948 2026-02-01 "codex頼んだ！"、R1@7376f14 2026-02-03 "大改修前"。
- R1@227ca48 2026-02-03 "task(P4-10): Extract exact value identification module"（`src/geosolver/_internal/solver/exact/pslq.py` 追加）。
- `task(P0..P4-*)`、`refactor/p*`、`fix/p0-*` ブランチ群（02-05〜）。R1@57a3dba 2026-02-23 "checkpoint" で型付き `MP_IsTangent(obj1: object, obj2: object) -> mpf`。
- R1@fe69e61 02-28 "after remediation planv4"、R1@31e0cce 03-01 "after remediation v5"。

### フェーズC: R1 外部ライブラリ統合・最適化器（2026-03-02〜04-03）
- R1@0284ee2 03-02 "before experience to decide whether introduce libraries"（`docs/EXPERIMENT_PLAN_EXTERNAL_LIB_PILOT.md` に NOMAD/DiscoMADS 記載）。
- R1@13c1b57 03-02 "before execute integration plan"（`EXTERNAL_LIBRARY_INTEGRATION_EXECUTION_PLAN.md`）。
- R1@a238648 03-05 "after external libs integration": `nomad_backend.py`、`nomad_blackbox_adapter.py`、`mpmath_refiner.py`、`select_rescue_boxes.py`、`run_phase_rescue_search.py` とそのテストを追加。
- R1@c62e309 03-25 "Finalize optimizer V9 evidence package"、R1@e4ba6ad 03-25 "pipeline: merge legacy hybrid phasea"（`SEARCH_MODE_HYBRID_LEGACY_NOMAD`）、R1@47d4b2a 03-28 既定探索モードを `hybrid_legacy_nomad` に変更。
- R1@2619f81 03-30 "Add baseline search policy contract"（`SEARCH_ATTEMPT_HYBRID_FALLBACK`）。`candidate/*` 31ブランチ（03-30〜04-02、例 `candidate/solver-staged-homotopy-r1..r9`）。

### フェーズD: R1 solver基盤の取り込みとAIMO3/Kaggle実験（2026-04-04〜04-15）
- R1@1fccda5 04-04 "Import solver baseline from staging (C:\Users\bakat\OneDrive\ドキュメント\geosolver\_solver_staging_20260404_035643)"、R1@80de696 04-04 "create solver-minimal baseline branch"。
- R1@5db9835 04-05 "Add AIMO3 Geosolver submission notebook with dual LLM+geometry pipeline"。exp05〜exp11、`aimo3-*`/`copilot/aimo3-*` ブランチ。最終 commit は R1@5f91713 系 2026-04-15（`aimo3-conservative-hardening`）。

### フェーズE: R4別系統（2026-04-25〜05-14、468 commit）
- R4@e55fb83 04-25 "docs: add geosolver research design"→R4@79a3fa5 "feat: scaffold geosolver package"→DSL AST、IR v2（R4@8a5cddb 04-26 "feat: add typed ir v2 catalog"）。
- R4@89aed16 05-06 "core: add msolve exact backend"、R4@0682e48 05-07 "fix: make msolve the core exact backend"。theorem-core 系ブランチ（05-06〜05-14）。R4@1c5c37c 05-14 "chore: preserve local master wip snapshot"。

### フェーズF: Rust 系 R2・R0（2026-07-04〜07-09）
- R2@4fc4406 07-04 "P0 clean-room guardian authority reset"〜R2@fdf1e0d 07-05 "Record R10 closure hash"（P0〜P9, R0〜R10 の段階 commit）。
- R0@212da9f 07-05 "Implement geosolver core through P5"、R0@4647ac5 07-06 "FCR-P0 import full core repair overlay"、R0@412f31d 07-08 "empty main"、R0@a4e8696 07-09 "Implement P1-P13 spec gap fixes"。
- R2/R0 と R1/R3 を結ぶ import 記録は commit message 上に見つからない。

### フェーズG: R3 clean-slate研究期（2026-07-10〜07-13、331 commit）
- R3@4749153 07-10 "chore: ratify clean-slate solver charter"（R3の唯一のroot）。`research(jac)`、`research(singular)`、`research(discovery)` 等。Julia（GeoTarget）実装を含む。
- R3@c157254 07-12 "feat(exact): add owned PSLQ recognition"（`julia/GeoTargetExact/src/pslq.jl`）。R3@5460cf3 07-12 "docs: add final solver research handoff"。

### フェーズH: R3 champion凍結と製品化（2026-07-27〜08-26）
- 07-14〜07-26 はR3にcommit無し。
- R3@05439a7 07-27 "research: freeze champion experiment evidence"（`experiment-freeze/20260727/`。README: 2026-07-22 の `champion_v2_poc_preloaded` が 145問中131の厳密目標集合を受理。外部アーカイブ元として `/home/kabatan/work/solver` と `/home/kabatan/work/geosolver` を記録）。
- R3@19a6e4e 07-27 "feat: productize frozen champion solver": `src/geotarget/_engine/runtime/geosolver/src/geosolver/_internal/...` に `nomad_backend.py`、`mpmath_refiner.py`、`select_rescue_boxes.py`、`run_phase_rescue_search.py`、`baseline_search_policy.py`、`exact/pslq.py` 等を追加（1431 files changed）。
- R3@0967ff1 07-29 "feat: ship qualified optimized champion solver"、07-30〜31 `origin/experiment` に `experiment:` 203件。
- R3@3803701 08-04 "Add research homotopy continuation baseline"、R3@6e15a9d 08-22 "fix: align main solver with experiment runtime"、R3@a5045c6 08-24 "refactor(package): unify distribution under geosolver"、R3@8ea1e13 08-24（`origin/main` 先端）、R3@7b2ebf1 08-26 "fix: restore NOMAD backend and high-precision polar"。

### フェーズI: R3 research への移植とsolver-a0凍結（2026-08-29〜08-31）
- R3@76ce993 08-29 "docs(research): add JSSA report and experiment plan"。
- R3@faf43a8 08-30 "research: replace legacy solver with cleaned pipeline and 323-case corpus": 本文 "Import the current codex/solver-hardening worktree, including its uncommitted fixes"。`RESEARCH_IMPORT.md` に移植元 `/home/kabatan/work/solver`・`codex/solver-hardening`・HEAD `c079b134…`（未commit修正込み）、移植前research `a3a915f`、バックアップ `codex/research-before-import-20260830` を記録。src 224ファイルが移植元とbyte一致と記載。
- R3@9d2d328 08-31 "docs(research): freeze solver-a0 baseline"（tag `solver-a0`）。

### フェーズJ: 9月〜10月（PC上のgit履歴はほぼ空白、archive に記録）
- R3@2b096ab 09-08 "Archive research solver and GMB experiments with local artifact inventory"（`origin/experiment`）。`archive/research-before-cleanup-2026-09-07` に保存と記載（このrefはPC上に無い）。
- 09-08〜10-21 の commit は R3/R4 に無い。以下は archive 内ファイルの記録:
  - `research-archives/solver-evidence/solver-analysis/`: 9月の機構分析。対象は research worktree の commit `e703e2d9…`（PC上に無い）。
  - `research-archives/2026-10-21/snapshot-manifest.json`: 10/21時点のresearch HEAD `754b5e3f…`（PC上に無い）。`docs/research/*-2026-09-22`〜`research-reset-2026-10-08`（Qwen学習実験等）と `algebraic_branches.py` などが未追跡（`??`）と記録。
  - `research-archives/solver-evidence/optimization-20261011/final-report.json`: 2026-10-11 に `candidate-v8-source` を採用（§5）。
- R3@052a477 10-21 "Archive research working tree and local assets before core cleanup"、R3@7b6691b 10-22 "Publish curated GeoSolver performance and mechanism evidence"（`origin/experiment`）。
- R3@1aa9139 10-22 "Publish current solver and benchmark core"（親 9d2d328）: 本文 "Consolidate the unpublished research history… byte-identical to research at 53c89957…. Full original local history is retained on codex/research-before-publish-20261022." "1650 tests passed"。53c89957 はPC上に無い。
- R3@978e778、R3@60db4b6 10-22（CI修正）。60db4b6 が現行凍結solver。

## 3. 機構ごとの初出表

全repo中の最早を太字。`-S`は文字列出現、「追加」は`--diff-filter=A`。

| 機構 | 初出日 | repo | commit | メッセージ／備考 |
|---|---|---|---|---|
| NOMAD（文書上の初出） | **2026-03-02** | R1 | 0284ee2 | "before experience to decide whether introduce libraries"（`-S NOMAD`、計画文書） |
| PyNomad/PyNomadBBO（文字列初出） | 2026-03-02 | R1 | 13c1b57 | "before execute integration plan"（計画文書） |
| nomad_backend.py（コード追加） | **2026-03-05** | R1 | a238648 | "after external libs integration" |
| 同上 | 2026-07-27 | R3 | 19a6e4e（-S初出は05439a7同日） | "feat: productize frozen champion solver"。改行コード差を除きR1@fc2e39b(04-04)/be363ab(04-09)の同ファイルと一致 |
| hybrid探索（"Hybrid DE探索"） | **2026-01-19** | R1 | 7c22f17 | "かなり大規模な変更"（optimize_impl.py） |
| hybrid_legacy_nomad モード | 2026-03-25 | R1 | e4ba6ad | "pipeline: merge legacy hybrid phasea"（既定化は47d4b2a 03-28） |
| hybrid_fallback（テスト名） | 2026-03-30 | R1 | 7cadb13 | "phasea: stage primary fallback"（`test_run_external_pipeline_uses_hybrid_fallback_before_rescue`） |
| SEARCH_ATTEMPT_HYBRID_FALLBACK | 2026-03-30 | R1 | 2619f81 | "Add baseline search policy contract"。R3@19a6e4e版と改行コード差を除き一致 |
| hybrid_fallback（R3） | 2026-07-27 | R3 | 19a6e4e | 同上 |
| rescue（.py初出） | **2026-03-02** | R1 | 0284ee2 | legacy_optimize_engine.py |
| rescue探索（select_rescue_boxes / run_phase_rescue_search） | 2026-03-05 | R1 | a238648 | "after external libs integration" |
| rescue（R3, 文字列） | 2026-07-10 | R3 | 4749153 | "chore: ratify clean-slate solver charter"（文書） |
| rescue探索（R3コード） | 2026-07-27 | R3 | 19a6e4e | -S初出は05439a7同日 |
| fallback（文字列初出） | 2025-12-17 | R1 | d36b63b | "Faster!"（optimizer.py） |
| algebraic_branches | **2026-10-21** | R3 | 052a477 | "Archive research working tree…"（10/21 snapshot内）。research上は1aa9139（10-22）。R1/R2/R0/R4(1aa9139以外)には無し |
| 同（archive内の記録） | 2026-10-11 | R3 archive | （7b6691b内ファイル） | `overfit-audit-receipt.json`・`optimization-speed-20261011/source-snapshots.json` の baseline-source に `algebraic_branches.py` が含まれる |
| mpmath_refiner | **2026-03-05** | R1 | a238648 | "after external libs integration"（-S初出は13c1b57 03-02 計画文書） |
| 同上 | 2026-07-27 | R3 | 19a6e4e | R1版と75行差（最小差はR1@c42856a/be363ab） |
| PSLQ | **2025-12-17** | R1 | 2768733 | "first commit"（`algebraic.py` で `from mpmath import pslq`、README記載） |
| PSLQモジュール pslq.py | 2026-02-03 | R1 | 227ca48 | "task(P4-10): Extract exact value identification module" |
| PSLQ（R3, Julia） | 2026-07-12 | R3 | c157254 | "feat(exact): add owned PSLQ recognition"（R4にも同commit） |
| pslq.py（R3, Python） | 2026-07-27 | R3 | 19a6e4e | R1@80de696版と改行コード差を除き一致 |
| IsTangent（初出） | **2025-12-17** | R1 | 2768733 | `IsTangent(line, circle, tolerance=1e-12)`（geogebra.py） |
| IsTangent（R4） | 2026-04-26 | R4 | 3257dfe | "docs: plan experiment platform ir v2" |
| IsTangent（R3） | 2026-07-27 | R3 | 19a6e4e | -S初出は05439a7同日 |

### IsTangent の実装変更履歴（記録されたもの）
1. R1@2768733 2025-12-17: `IsTangent(line, circle, tolerance)`（geometry/compat/geogebra.py）。
2. R1@269a1f8 2026-01-28 "うーん": `IsTangent(obj1, obj2)`（operations/basic.py）と `MP_IsTangent(obj1, obj2)`（mp_api.py）を追加。R1@ec1927d 01-22 で旧 geogebra.py 版は archive 配下から削除。
3. R1@57a3dba 2026-02-23 "checkpoint": `MP_IsTangent(obj1: object, obj2: object) -> mpf` に型付け。
4. R3@6e15a9d 2026-08-22 "fix: align main solver with experiment runtime": mpmath_refiner に「`Distance(P,Q)` と公開 `IsTangent` は非負で解で微分が0/未定義になるため、局所高精度精密化に限り等価な滑らかな残差に置換する」関数を追加。
5. R3@1aa9139 2026-10-22（squash commit）: `geometry/mp/signed_tangency.py`（「IsTangentと同じ絶対値・定義域で零点の尖りを持たない」符号付き残差）と `problem/tangency_contacts.py` を追加し、mpmath_refiner の置換を `signed_tangency` に変更。`analytic_jacobian.py`・`cartesian_polynomials.py`・`algebraic_branches.py` でも `IsTangent` を扱う。公開 `MP_IsTangent`／`operations/basic.py` は 9d2d328→1aa9139 間で変更なし。
   - archive の記録: `signed_tangency.py` は9月機構分析の対象 commit e703e2d の source-files.json に既に含まれ、10/21 snapshot では追跡済み。`tangency_contacts.py` は 2026-10-11 の overfit-audit-receipt.json に記載があり、10/21 snapshot では未追跡。いずれも元 commit はPC上に無い。

## 4. 系統の関係（記録されている範囲）

- R1 → R3: R3@19a6e4e（2026-07-27）が `src/geotarget/_engine/runtime/geosolver/src/geosolver/_internal/` 以下に置いた `nomad_backend.py`・`select_rescue_boxes.py`・`run_phase_rescue_search.py`・`baseline_search_policy.py`・`exact/pslq.py` は、改行コード差を除いてR1の同名ファイル（R1@fc2e39b, be363ab, 80de696, 2619f81 等、2026-03-30〜04-09）と一致。blob hash は一致しない（改行コードの違い）。R3の commit message に R1（kabatan/GeoSolver）からの import 記述は無い。
- R3 `research` ← `codex/solver-hardening`: R3@faf43a8（2026-08-30）が `/home/kabatan/work/solver` の `codex/solver-hardening` 作業ツリー（HEAD c079b134 + 未commit修正）を取り込んだと `RESEARCH_IMPORT.md` に記録。c079b134 はPC上に無い。
- R3 `research` 9d2d328 → 1aa9139: 9月〜10月の作業履歴は squash され、元履歴は `codex/research-before-publish-20261022` に保持と commit message に記録。
- R4 = R3の `research` と同一の research ブランチ + 2026-04/05 の別root系統（R3には無い）。
- R2・R0（Rust）: R1/R3/R4 との import 関係を示す commit message・共通commitは見つからない。

## 5. 指定ブランチの有無

調査方法: R0〜R4（およびWSL `~/work` の全repo）で `git for-each-ref`、`git branch -a`、`git reflog --all`、`.git/packed-refs`、`.git/logs/` を検索。

| ブランチ | PC上のref | 記録されている場所 |
|---|---|---|
| `codex/research-before-publish-20261022` | 無し | R3@1aa9139（2026-10-22）の commit message のみ |
| `codex/solver-hardening` | 無し | R3@faf43a8（08-30）の `README.md`、`RESEARCH_IMPORT.md`、`RESEARCH_IMPORT_MANIFEST.json`（"source_branch"）、`benchmarks/repairs/corpus97/README.md`、commit message。c30f97d・de0e90f（08-30/31）で削除 |
| `codex/research-before-import-20260830` | 無し | R3@faf43a8 の `RESEARCH_IMPORT.md`・`RESEARCH_IMPORT_MANIFEST.json`（"previous_research_backup_branch"）。de0e90f で削除 |

参考: 名前の似たref `aimo3-conservative-hardening`（R1, 2026-04-15）、`archive/research-before-cleanup-2026-09-07`（R3@2b096abの文書に記載、refは無し）。

## 6. solver-experiment／候補v1〜v8

**ローカルの `solver-experiment` ディレクトリ・`optimization-20261011` ディレクトリはPC上に見つからず。**
探した場所: `C:\Users\bakat`・`C:\`（深さ4）、WSL Ubuntu の `~`（深さ4）と `/`（深さ5, root権限）。git内の記録では元の保存先は `/home/kabatan/work/solver-experiment/research-archives/2026-10-21/local/original-tree/benchmarks/local-evaluation/optimization-20261011/`（R3 `docs/archive.md`）。

R3 `origin/experiment`（7b6691b）の `research-archives/solver-evidence/optimization-20261011/` に取り込まれた記録（2026-10-11、323問・180秒・1コア/問）:

| 版 | 記録 | 一致数 | 実時間中央値 | 合計 |
|---|---|---|---|---|
| baseline（seed 0） | final-report.json `baseline_fresh_seed0` | 309/323 | 6.183 s | 8813.65 s |
| candidate-v8（採用, seed 0） | `final_by_seed.0` | 321/323 | 2.997 s | 4705.76 s |
| candidate-v8（seed 1） | `final_by_seed.1` | 320/323 | 3.198 s | 5012.18 s |
| candidate-v8（seed 2） | `final_by_seed.2` | 317/323 | 3.202 s | 4297.55 s |
| candidate-v8（3 seed計） | `final_public` | 958/969 | 3.124 s | — |
| holdout 48入力 | snapshot/README.md | 38/48→48/48 | 2.650→0.858 s | — |

- 目標「完全一致99%以上」「中央値1秒未満」はいずれも false と記録（`goals`）。
- v1〜v7 の段階別測定値は git 内に無い。名前が出るのは `candidate-v6-source`（overfit-audit-receipt.json、source hash `78c9ec7b…`）と `candidate-v8-source`（採用）のみ。同日の追加高速化（`optimization-speed-20261011/`）の試作版 `refinement-fallback-v4`、`analytic-stable-v3` は「採用なし」と記録。
- WSL `~/work/bisect/`（2026-10-22作成）は `source-snapshots.tar.gz` から展開した作業ディレクトリで、v1〜v8 の測定値は含まない。

## 7. 不明点

- `codex/research-before-publish-20261022`・`codex/solver-hardening`・`codex/research-before-import-20260830`、commit 53c89957・c079b134・754b5e3・e703e2d はPC上に無い（GitHub上か別PCのWSLにある可能性があるが未確認）。そのため 2026-09-08〜10-21 の commit 単位の履歴、および `algebraic_branches`・`signed_tangency`・`tangency_contacts` の正確な初回 commit は特定できない。
- R1→R3 のコード移動は内容一致から確認できるのみで、移動を記録した commit message は無い。R2・R0（Rust）と他系統の関係を示す記録は無い。
- R4 別系統（2026-04-25〜05-14）と R1 の関係を示す記録は確認していない。
- 2026-07-14〜07-26 は R3/R4 に commit が無い。この期間の実験（EXP-V15-243 等）は R3@05439a7 の文書にのみ記録される。
- 日付は author date。rebase・squash 済みの commit は元の作業日時と異なる可能性がある（1aa9139 など）。
