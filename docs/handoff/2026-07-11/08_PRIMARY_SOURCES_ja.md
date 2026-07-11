# 一次資料と GeoTarget への適用境界

この文書は algorithm 候補を「既存手法の名前」だけで選ばないための短い routing table である。網羅版は `docs/research/LITERATURE_MATRIX.md`。新しい algorithm family を試す前に、仮定・破綻条件・対照実験を一行追加する。

## 1. 最優先の local globalization

| source | primary result / interface | GeoTarget で使う部分 | そのまま成立しない点 |
|---|---|---|---|
| [Moré, The Levenberg–Marquardt Algorithm: Implementation and Theory (1978)](https://doi.org/10.1007/BFb0067700) | implicit variable scaling と safeguarded damping を含む robust LM implementation | 固定 magic lambda をやめる scale-aware damping comparator | C1 smooth NLS の local model。opaque C0、guard/domain、singular root、all-root discovery を保証しない |
| [Transtrum & Sethna, Improvements to the Levenberg–Marquardt algorithm (2012)](https://arxiv.org/abs/1201.5885) | narrow canyon/flat model での LM 改良、uphill acceptance/geodesic acceleration | model agreement と damping update の仮説 | branch/nonsmooth semantics と false root acceptance は別問題 |
| [NonlinearSolve.jl paper (2024)](https://arxiv.org/abs/2403.16341) | Julia nonlinear/root/NLS solver の統一 interface と solver comparisons | external LM/TR reference、adapter semantics | library retcode は GeoTarget truth でなく、canonical endpoint gate が必要 |
| [NonlinearSolve least-squares solver guide](https://docs.sciml.ai/NonlinearSolve/stable/solvers/nonlinear_least_squares_solvers/) | LM、Gauss–Newton、Trust Region の official options | ALG-LAB-001 reference configuration | positive-residual stationary point、rank-deficient manifold、guard/branch を処理しない |
| [Coleman & Li, An Interior Trust Region Approach for Nonlinear Minimization Subject to Bounds (1996)](https://doi.org/10.1137/0806023) | bound-constrained nonlinear minimizationの interior trust-region framework | bound-aware step/radius の設計参考 | residual root 発見や全解回収、black-box semantic validity の定理ではない |

最初の結論は「TR を採用」ではなく、「現行 damping/globalization を同 accounting で比較する」である。

## 2. endpoint accuracy / rank / singularity

| source | relevant result | planned use | break condition |
|---|---|---|---|
| [Tisseur, Newton's Method in Floating Point Arithmetic and Iterative Refinement of Generalized Eigenvalue Problems (2001)](https://doi.org/10.1137/S0895479899359837) | residual/Jacobian/linear solve error下の Newton limiting accuracy | residual、correction/forward error、target error を別 artifact にする | singular root では regular inverse bound が成立しない |
| [Ipsen, Kelley & Pope, Rank-Deficient Nonlinear Least Squares (2011)](https://doi.org/10.1137/090780882) | numerical rank ambiguity が NLS accuracy を壊す | two-stencil rank stability、CPQR/SVD controls | fixed cutoff を universal route にできない |
| [Decker & Kelley, Broyden at singular roots (1985)](https://doi.org/10.1137/0722034) | 特定 singular class/initial region で local linear convergence | diagnosed research control のみ | global/all-root/general black-box guarantee ではない。既存 S3 は budget gate fail |
| [Shen & Ypma, Newton method for singular systems (2005)](https://doi.org/10.1016/j.apnum.2004.09.029) | generalized-regular singular root で bordered nullspace system | stable rank trigger 後の R4 candidate | manifold、wrong nullity、noisy rank transition、unavailable derivative |
| [Lee, Li & Zhi, two-step method for deflation-one singular zeros (2024)](https://doi.org/10.1016/j.jsc.2023.102278) | range/nullspace correction で local quadratic convergence | representation-stable S4 successor の理論 control | sufficiently-close、deflation-one、analytic/second derivative の仮定。既存 candidate は metamorphic gate fail |
| [Bates et al., Adaptive Multiprecision Path Tracking (2008)](https://doi.org/10.1137/060658862) | conditioning/accuracyに応じた precision adaptation | candidate-seeded precision ladder | homotopy path の結果であり、arbitrary local NLS/root certificate ではない |

`condition-guided symmetric weak-direction exploration` は、上記の SVD/nullspace literature から「弱方向は局所幾何の情報を持つ」という着想を借りるが、既存定理から all-root recall が従うとは主張しない。GeoTarget 固有の empirical proposal hypothesis として、isotropic-probe control、representation replicas、manifold/guard counterexamples、charged work で検証する。

## 3. all-root discovery

| source | relevant result | planned experiment | claim boundary |
|---|---|---|---|
| [Sobol, low-discrepancy sequences (1967)](https://doi.org/10.1016/0041-5553(67)90144-9) | cube内の low-discrepancy sequence | deterministic start-source control | root basin capture、random confidence、probabilistic completeness を与えない |
| [Owen, scrambled nets (1997)](https://doi.org/10.1137/S0036142994277468) | randomized scrambling と variance analysis | Owen-scrambled Sobol empirical comparator | integration theorem であり、points は IID でなく root capture theorem ではない |
| [Henderson et al., Topographical Global Optimization (2017)](https://doi.org/10.1016/j.apnum.2016.10.007) | Sobol + kNN topograph で local starts を選択 | hard discard でなく soft order/defer | close roots、narrow basins、nonzero minima、invalid semantics |
| [Rinnooy Kan & Timmer, MLSL (1987)](https://doi.org/10.1007/BF02592071) | bounded multi-start clustering の解析 | duplicate-allocation の historical control | finite separated minima 等。manifold/close target へ直接適用不可 |
| [Larson & Wild, APOSMM (2018)](https://doi.org/10.1007/s12532-017-0131-4) | asynchronous multistart と一定仮定下の結果 | all sampled points を考慮する soft emitter idea | hard close-root suppression を正当化しない。independent-uniform insurance を残す |
| [Hansen et al., COCO (2016)](https://arxiv.org/abs/1605.03560) | fixed-target anytime runtime distribution | prefix curve、ERT/ECDF、budget-censored comparison | target/tolerance/costを結果後に変えると比較不能 |

full-support claim は materialized independent-uniform D0 lane の `p_i>0` と scheduler fairness という条件付き capture argument にだけ付ける。current `iid`-labelled counter stream、QMC、ordering の gain は empirical とする。

## 4. archive / deflation

| source | relevant result | allowed use | required counterexamples |
|---|---|---|---|
| [Farrell, Birkisson & Funke, Deflation techniques for finding distinct solutions (2015)](https://doi.org/10.1137/140984798) | known isolated solution を避ける shifted residual deflation | independent numerical-root evidence または C3V 等で isolated-solution assumption を支えた witness に限定 | manifold、unknown multiplicity、close root、target collision、nonzero minimum |
| [Bloor Riley, Webb & Baker, Deflated Gauss–Newton (2025)](https://doi.org/10.1137/24M1695191) | full-rank assumptions下の deflated GN step | full-rank diagnosed research control | rank-deficient root、guard/branch、spurious optimization solution。既存 v2 は development gate fail |

acceptance は常に undeformed canonical residual で行う。既存 root/target を避ける search model と、正しさの predicate を混同しない。

## 5. derivatives / sparse computation

| source | relevant result | planned use | break condition |
|---|---|---|---|
| [Revels, Lubin & Papamarkou, Forward-mode AD in Julia (2016)](https://arxiv.org/abs/1607.07892) | dual-number forward AD implementation | C1/native Julia plugin comparator | foreign callback、hard type assertion、nondifferentiable branch |
| [DifferentiationInterface paper (2025)](https://arxiv.org/abs/2505.05542) | common AD frontend/preparation | compiled oracleごとの prepared backend | shape/plugin change、wrapper overhead、C0 capability |
| [Coleman & Moré, Estimation of Sparse Jacobian Matrices (1983)](https://doi.org/10.1137/0720013) | graph coloringによる FD grouping | conservative compiler sparsity + cached color | missing dependency は silent wrong Jacobian。dense differential test 必須 |
| [SparseDiffTools official documentation](https://docs.sciml.ai/SparseDiffTools/) | current Julia coloring/Jacobian interface | implementation reference | callback reductionだけでは cold/dense overheadを正当化しない |
| [Julia Performance Tips](https://docs.julialang.org/en/v1/manual/performance-tips/) | type stability、preallocation、function barrier | compiler/oracle profiling後の低リスク改善 | open plugin call、compile-size/latency tradeoff |

過去 sparse-coloring experiment は一般 default gate を落とした。fresh cached/applicability study なしに production へ戻さない。

## 6. validation

| source | relevant result | planned use | limitation |
|---|---|---|---|
| [Rump, Verification methods (2010)](https://doi.org/10.1017/S096249291000005X) | floating computation から rigorous enclosure を作る方法 | optional C3V local verifier | outward interval/derivative enclosure が必要。BigFloat point replay ではない |
| [Breiding, Rose & Timme, Certifying zeros of polynomial systems (2020)](https://arxiv.org/abs/2011.05000) | interval Krawczyk による isolated nonsingular root certificate | polynomial/C3V-capable local control | arbitrary opaque C0、singular/manifold、target identity/all-root proof へ一般化しない |
| [IntervalRootFinding.jl official roots interface](https://juliaintervals.github.io/IntervalRootFinding.jl/latest/roots/) | interval Newton/Krawczyk、`unique`/`unknown` | optional backend implementation reference | package status は owned replay artifact で再計算する |

C3V は solver discovery の前提にせず、candidate 後の optional assurance lane とする。

## 7. 添付 plan v2 から残す数値案

`C:\Users\bakat\Downloads\research_plan_v2_ja.md` の Theory 部分は今回の roadmap から除外する。一方、次の数値仮説は measured trigger 付きで残す。

- typed geometry DAG compiler — oracle profile が支配的な場合
- nested evaluation と lifted sparse factor graph の二 view — deep chain/branch/basin failure が残る場合
- target adjoint — local target error/precision allocation の補助 signal
- configuration/constraint homotopy — direct capture failure が local champion 後も残る場合
- lazy branch-and-track — branch switch が主要 failure の場合
- problem passport — case ID でなく public numeric diagnostics だけで routing できる場合

これらは plan の良い要素を失わず、現時点の第一実装に固定しない形で R4/R5 queue に保存している。

## 8. citation rule

- technical claim は paper/official documentation の一次資料へ直接 link する。
- source の theorem 仮定と GeoTarget の破綻条件を同じ行に書く。
- benchmark leaderboard、blog、library popularity だけで production promotion しない。
- paper の local convergence を global/all-root claim へ拡大しない。
- 新 paper/library version を加える場合は、current official API を再確認する。
