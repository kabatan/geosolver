# スーパーPC全体スイープ（2026-10-22）

調べた範囲: このPC（Linux）の `/home/kabatan` 以下と `/var/tmp`、`~/.codex`、`~/.claude`、各repoのgit（solver、solver-experiment、geosolver）。名前に geosolver が入らないフォルダも含めます。サブエージェント3本（`~/work` 他、`~/ドキュメント` 等、Codex会話記録）の報告は、私が一部を原文で確認しました（確認したものに「確認済」と付けています）。読んでいないものは「未読」としました。

## 先に分かったこと

1. **`~/work/solver-experiment` は experiment ブランチのチェックアウトで、設計経緯の文書が最も多い場所です**（GeoTarget系。READMEの91行目に「measured source is GeoSolver, not GeoTarget」の注意あり）。レポート3章は現行 GeoSolver が対象なので、「同じ着想の起源・同時期の判断」として使い、GeoSolver 本体の記録と混ぜない扱いを勧めます。
2. NOMAD 採用理由の原文は、このPCにはありません。Windows側の `r1-design-rationale.md`（71c15bb）を使ってください。
3. 「自由度圧縮」の最初期の記録は、solver 本体ではなく **DSL作成側のゲージ固定**（`DOF_COMPRESSION_AUDIT.md`、2026-08-05）です。solver 本体の `positive_scale_chart` は 2026-10-11 が初出です（`candidates-v1-v8.md`）。
4. ChatGPT の会話エクスポートと `geosolver_optimization_proposal.md` は、このPCのどこにもありません。2026-07-09 より前の記録は、TeXstudio のキャッシュ1件だけです。
5. `~/.claude/projects` の記録（約50件）は、パチンコ・Yamikoma・AIdesigns・PARC 系で、solver 無関係です（先頭のユーザー発言を全件確認済）。

## 一覧（場所・中身・3章で使えるか）

凡例: ◎ 3章の中心資料、○ 補強に使える、△ 背景のみ、× 不要

| 場所 | 中身の要約 | 3章 |
|---|---|---|
| `~/work/solver-experiment/docs/GEOSOLVER_RESEARCH_SUMMARY_ja.md`（58KB、コミット `421e67933`/`15f6eaf68`、2026-08-24。experimentブランチ） | solver とは何か（§2）、低次元化と意味保存（§3.2）、champion のアルゴリズム Step 0〜8（§7）、研究の流れ（§9.1〜9.9: baseline、R0–R7 roadmap、local solver 比較、「residualだけではrootの正しさにならない」§9.4、不採用候補§9.6、champion v0→v1→v2）。確認済の引用: 「性能のために数学的に同値そうな別問題へ置き換えてはいけない。」（§3.2。許される低次元化は平行移動・回転のgauge、carrier上のparameterization、sourceが明示したconstructionのみ） | ◎（GeoTarget系） |
| `~/work/solver-experiment/docs/handoff/2026-07-11/01_OWNER_DIRECTIVES_AND_SCOPE_ja.md`（`5460cf396`、2026-07-12） | 設計判断の記録 OD-01〜OD-17。確認済の引用 OD-02: 「幾何を連立方程式化すると変数が非常に多くなり、RUR/Gröbner 等の全面 exact solver は現実的な main route になりにくい。」→「小さい capability-specific backend、truth 作成、局所 certificate、比較 control に限定する」。同フォルダの `03_BASELINE_AND_PRIOR_EVIDENCE_ja.md`、`04_ALGORITHM_RESEARCH_ROADMAP_ja.md` は未読 | ◎（設計判断の理由） |
| `~/work/solver-experiment/research/datasets/competition_geometry_20y/`（コミット `94aa68c4e` 2026-08-04、`15370d2f8`/`edb6ab7f0` 2026-08-05 ほか。experimentブランチ） | GeoSolver の不具合修正の報告群（2026-08-03〜08-22）。`MPMATH_REFINER_HIGH_PRECISION_FIX.md`（確認済: direct_evaluation の1e-15判定が厳密化処理を迂回する不具合、`findroot` の最終残差の未確認、1変数複数制約でresidual index 0だけを使う不具合を修正）。`DOF_COMPRESSION_AUDIT.md`（確認済: 302件のDSLの独立変数が0〜7、「定理による数値短縮（方べき、Ptolemy、角の二等分線定理など）は行っていない」）。`PERFORMANCE_DIAGNOSIS.md`、`STRICT_GUARD_FIX_REPORT_2026-08-05.md`、`RANK_AWARE_CLOSURE_FIX_REPORT_2026-08-12.md`、`AFFINE_PI_EXACTIFICATION_FIX_REPORT_2026-08-12.md`、`EXACTIFICATION_FACTOR_FIX_REPORT_2026-08-12.md`、`BENCHMARK_REPORT_180S_1CORE*.md` は一覧のみ・未読 | ◎（mpmath refiner・厳密化の修正経緯） |
| `~/work/solver-experiment/research/experiments/EXP-LOCAL-008`（`dca5f17ab`/`77effffc9`、2026-07-12）と `docs/research/LITERATURE_MATRIX.md` | NOMAD系（OrthoMADS）の事前登録比較。T0で不採用（回復1対照5、作業量1.47倍。サブエージェント報告、判定ファイルは私は未開封）。文献表に NOMAD/MADS の行あり（確認済: Audet & Dennis 2006、NOMAD 4） | △（GeoTarget系の比較。GeoSolver の NOMAD 採用理由ではない） |
| `~/work/solver-experiment/CHARTER.md`、`docs/adr/0001-0003`（2026-07-10） | clean-slate の憲章と ADR。ADR-0003「PSLQ/minimal-polynomial recognition is only a proposal step」（確認済）。`docs/research/EVIDENCE.md` に EVID-01〜11（残差だけの開始点選択は不採用、など。確認済） | ○（GeoTarget系） |
| `~/work/solver`（git）experimentブランチ | 386コミット（ブランチ固有）。7/10〜7/13 lab、7/27 champion凍結(`05439a7b0`)、7/29 optimized(`0967ff1cd`)、7/30〜31 に約330コミット（`experiment:`/`audit: stop` が大半＝不採用候補の検証）、8/11 に `codex/exp-*` 等のブランチを archive merge で統合（`ba2ea3130`、一覧は `experiment-freeze/20260811/BRANCH_CLEANUP.md`）。`docs/research/NEGATIVE_RESULTS.md` に負の結果の台帳の方針 | ○（試して外した候補の存在の証拠）。`codex/solver-hardening` の名前は一覧に無し |
| `~/work/solver-artifacts/main-cleanup-20260729/geotarget_solver_algorithm_theory_v5〜v9`（TeX/PDF、2026-07-29/30） | GeoTarget の算法理論資料。`NOVELTY_MAP.md` は理想理論と main の実装を区別（256 starts × 600 callbacks、direct-Broyden LM/TR、endpoint reservoir、owned_pslq、512/768/1024-bit refinement。サブエージェント報告）。v7・v8は未読 | ○（GeoTarget系の設計進化） |
| `~/work/solver-artifacts/numerical-robustness-audit-20260729/NUMERICAL_ROBUSTNESS_AUDIT_20260729.md` | 145件で1-ULP摂動の監査、失われた答えなし（冒頭のみ読了） | △ |
| `~/work/solver-experiment/research-archives/solver-analysis/`（2026-09、`solver-evidence/README.md`が入口） | 9月の機構分析。日本語報告書 `report/research-report-ja.md`/`.pdf`、`development/`（接触検出器、damping campaign、representations 等）、`history/` | 3章では×（9月の研究方向の検討。前回の調査では未精読） |
| `~/work/solver-research-assets/workspace-before-research-root-20260830/snapshot/SOLVER_*.md`（2026-08-30） | `SOLVER_PIPELINE_CLEANUP.md`（確認済）ほか4本（REGRESSION_FIXES、REAUDIT_IMPLEMENTATION、FINAL_AUDIT_FIXES、BOUNDARY_AND_HANDOFF_FIXES）。8/30の最終監査の修正記録。後の4本は題名のみ・未読 | ○ |
| `~/work/solver-research-assets/{corpus97-*, gmb-campaigns, gmb-comparison-source-materials, jssa-source-materials}` | 評価用コーパスとGMB比較の入力。開いたのは一覧のみ | △（評価章向け） |
| `~/work/solver-experiment-results/`（144項目の生JSON、markdown無し） | s1-multitarget、rank-chart、struct-poly、scheduler-hybrid などの実験の生出力（名前のみ確認） | △ |
| `~/work/geosolver`（7/9のrepo） | 前回報告のとおり。`docs/SOLVER_REFACTORING.md`、`docs/reports/OPTIMIZATION_REPORT.md` 等（確認済） | ○ |
| Codex会話記録の要約 `jssa/history/superpc-sweep-codex-digest.md`（本文はそちら、約46KB） | 2026-08-22〜10-21 の work/solver セッション50件のうち、利用者の発言と設計・測定の説明を時系列で抜粋し、[CH3]（3章で使える）/[CH3-ctx]/[NO] を付けたもの。要点: 8/23〜24 に監査で「出荷不可」→GeoSolver へ改名、8/25〜26 にベンチ作成で見つかったバグの切り分け（DSLバグかsolverバグか）、8/26 に PyNomadBBO==4.5.1 を追加（`7b2ebf12`）して NOMAD を復活（PyNomad欠如でSciPyにフォールバックし候補0件だった）、8/30 の最終監査、`solver-a0`/`solver-a1`（`fd2c9a5f`）、利用者の設計方針「PhaseCですべての解を回収する仕様とかにしたらsolverが終わらなくなります」（確認済）、9/7 の323問×3 seed（930/969、中央値7.21秒）、10/11 の最適化 | ◎（デジェストは要約。原文の行番号つき） |
| `~/work/solver-experiment/research-archives/2026-10-21/local/original-tree/benchmarks/local-evaluation/optimization-20261011/` | 10/11の候補ソース約80本と測定。`candidates-v1-v8.md` に整理済 | ◎ |
| `~/.config/texstudio/cache/geosolver_math_exposition_r_gdtpk_q_xelatex.json`（2026-07-07 18:26） | **7/9より前の唯一の痕跡**。元の `.tex`（`~/ダウンロード/geosolver_math_exposition_…tex`）は現存せず、目次だけ残る。「座標先行法 vs target 先行法」、projection DAG、Gröbner elimination（F4/F5）、resultant、quotient algebra、membership/annihilator/resultant certificate、代数的コスト削減、新規性の位置づけ、失敗状態（非有限 target image、AlgorithmicHardCase、CertificateDesignGap）。サブエージェント報告で、私は未開封。NOMAD・mpmath・PSLQ の最終設計とは別の、代数側の設計案に見える | △（利用者に.texの所在確認を勧める） |
| `~/aggregate-check.txt`、`~/preflight-with-reviews.json`（2026-09-03） | algebra_v2 ベンチ収集の集計（候補1314件・1083族、受理736件・証拠603族、8分野・6種別、各caseに担当と独立レビュー、coreとholdout、release_ready=false、geometry_cad は必要50族のうち14）。冒頭のみ読了（サブエージェント報告） | △（ベンチ構築の話。3章より評価章向け） |
| `~/ダウンロード/germ_engine.py`（2026-09-13）、`SOLVER_RESEARCH_BRANCH_AUDIT_COMPLETE.md`（2026-08-31）、`AIME_geometry_2000_2026_Prism.zip`（2026-08-22）、`志望理由書_山本一揮.pdf`、`情達ポスター発表原紙＿山本一揮.pdf` | germ_engine.py は t=0 での幾何DAGの厳密評価の試作（docstring「not the installed GeoSolver」）。監査md は対象ファイル0の空の自動監査。zip は問題源の可能性。2つのPDFは未開封（solver に触れている可能性） | △／未読 |
| `~/.bash_history` | 7/9以降 `cd work/geosolver`、のち `work/solver` と `uv run geotarget doctor`/`geotarget ui` | △（時系列の補助） |
| `~/tmp/geosolver-bench-case_wave13`、`/var/tmp/geosolver-archive-20260904-*`、`~/Documents/Codex/2026-09-07/new-chat/work/` | ベンチ収集の作業ディレクトリ、比較対象の外部ライブラリ（PHCpack、ibex-lib、opengv、PoseLib 等）、ディスク整理の棚卸し（geosolver-bench-* の worktree 一覧）。設計理由の文書なし | ×（比較対象の候補名としては使える） |
| `~/ドキュメント/{ChatGPT,Codex,FE solver,PARC2026,Surge XT}`、`~/Documents/Codex/*` | ChatGPT は Pachinko・localLLM・New project（パチンコシミュレータ）のみでGeoSolverのエクスポートは無し。Codexは数学オリンピックの証明セッション、3Dモデル等。FE solver は関数方程式用の別プロジェクト、PARC2026はロボティクス。サンプリングで確認 | × |
| `~/work/{ai_research,oracle,QF_NRA.*,rtb-*,source-rescue-*,non-econ-source-*,pydantic-temp,Pachikoma,Yamikoma,AIdesigns,…}`、`~/{artifacts,datasets,var,opt,tmp_evacuated_1018}` | 無関係（AlphaProof風の証明器、別CLI、別ゲーム等）か、ベンチ収集の素材（QF_NRA、source-rescue）。ベンチ収集は「solverの結果を使わない」方針（`source-rescue.report.json` の `solver_outcome_used: false`）のみ1文で引用可 | × |

## 見つからなかったもの

- NOMAD 採用理由、Phase A/B/C の命名、rescue/第2探索、`algebraic_branches`、`scale chart` の「なぜ」を書いた文書は、このPCのどのフォルダにもありませんでした。`algebraic_branches`・`scale chart` の理由は 2026-10-11 の会話記録（`candidates-v1-v8.md`、`dev-history-superpc.md`）、他はWindows側の旧repoの記録が頼りです。
- `codex/research-before-publish-20261022`、`codex/solver-hardening`、`codex/research-before-import-20260830`: このPCのgitに無し。
- ChatGPT の会話エクスポート、`geosolver_optimization_proposal.md`: 無し。
