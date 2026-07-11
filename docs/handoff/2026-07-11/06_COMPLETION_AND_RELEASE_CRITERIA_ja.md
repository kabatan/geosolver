# Solver completion と release criteria

## 1. 「完成」の意味

任意の smooth black-box nonlinear system について、有限時間で全実根を発見したと一般に証明することはできない。したがって GeoTarget の完成を「すべての入力を必ず解く」と定義しない。

完成とは、次を満たすこととする。

1. declared problem envelope と budget profile が明示されている。
2. 未知問題を含む frozen holdout で、全 distinct target を得る確率が高い。
3. accepted answer の誤りを独立 replay と adversarial controls で強く抑える。
4. finite search の未発見を `no_solution` と誤称しない。
5. black-box geometry DSL と plugin extensibility を保つ。
6. fixed-budget work/time が current baseline と旧 solver に対して測定可能に改善する。
7. algorithm、fallback、assurance level、failure status が簡潔で保守可能である。
8. raw evidence から release result を再現できる。

これは statistical/empirical completion であり、algebraic completeness proof ではない。

## 2. assurance level を分ける

| level | 意味 | 必要 evidence | 言ってはいけないこと |
|---|---|---|---|
| discovered endpoint | search/local solver の観測 | attempt trace | answer、root、exact value |
| provisional numerical answer | canonical semantics と independent high-precision/validated numerical recheck を通過 | replay-bound evidence + correction/error status | same-point replayだけでのroot existence、全 target 完備、algebraic exactness |
| validated configuration/target interval | sound C3V callback と box verifier が存在/一意性を示す | independently replayable interval artifact | singular/manifold/general C0 への一般化 |
| exact answer | configuration validity certificate + target identity certificate | `ExactAnswer` certificate pair | 未発見 target がないこと |
| search coverage statement | declared corpus/budget の empirical success または D0 independent-uniform に対する条件付き bound | run distribution / assumptions | finite-time universal completeness、current counter stream の joint IID 性 |

一般 C0 plugin でも solver discovery は使える。C3V/exact capability がないことを DSL 非対応にしてはならない。

## 3. declared release envelope

初回の general-performance envelope は既存 `M0_M4_BASELINE.md` を基礎にし、holdout で拡張する。

core envelope:

- bounded deterministic real problems
- 1–16 free variables
- 1–64 residuals
- 1–1024 construction nodes
- one real scalar target、finite expected target set
- C0 black-box evaluation、C1/C2 optional
- domain/guard/branch semantics を持てる
- regular、ill-conditioned、near-rank、overdetermined、close-root、target collision strata

diagnosed extended envelope:

- tangent / isolated singular root
- feasible manifold と target image
- strict guard boundary
- adaptive-unbounded shell
- plugin-private opaque/transcendental objects

extended stratum で完全回収できない場合も、false answer を返さず typed `unknown` と evidence を返せることを release 要件にする。scope を黙って縮めない。

## 4. milestone と exit

### G0 — algorithm-lab ready

現状: **ほぼ達成**。

達成済み:

- truth-blind variant API
- callback budget accounting
- paired saved starts
- representative baseline
- production research seam
- black-box C0 case

残り:

- assessor/reported local metrics
- legacy/prod-tol/prod-options local controls の区別

### G1 — local champion frozen

- LM/TR/globalization candidates を matched cumulative oracle-work thresholds と production wall budgets で比較済み。launch prefix だけを同 budget としない。
- globalization stage は common-assessor inconsistent endpoints を control より増やさず、correction/acceptance stage 後は reported-accepted Gold-inconsistent witness 0 または明示的 rejected/unknown。production validator の false promotion 0。
- T2 の family-equal `P_assessor_all_targets` / reported recall / work gate を通る。
- NearRank/Tangent の condition-aware behavior を定義。
- opaque C0 production-path smoke を通る。
- winner 以外の duplicate production routes を削除。

### G2 — discovery champion frozen

- local pipeline を固定して independent-uniform D0/current counter/QMC/ordering を比較済み。
- MultiRoot、close-root、target collision で enforced fixed case-total budget gain。
- permanent independent-uniform lane、refinement-exhaustion non-starvation、prefix monotonicity を確認。
- hard suppression なし、truth leak なし。
- duplicate work を測定し、archive/presentation semantics を確認。

### G3 — alpha solver

- U1/U2 holdout の production validation path で stable `P_full_validated`。
- production `ProblemSpecV1`/plugin/canonical path を通る。
- 60/180/420 s anytime curve を出せる。
- no P0/P1 correctness bug。
- one default local path + bounded diagnosed rescue lanes。
- user-facing status、unknown、assurance level が明確。

### G4 — beta general solver

- U3 unknown family と U4 new plugin holdout を通る。
- real geometry corpus を truth-audited subset で評価。
- 30 seeds/finalist の paired production campaign。
- compiler/JIT/oracle/local/scheduler の cost attribution。
- provisional target collision presentation が一貫。
- predeclared exact-eligible corpus で、capability-specific exact promotion/replay path を評価。全面 RUR は要求しない。
- full CI、Nightly fuzz/metamorphic、replay portability を通る。

### G5 — release candidate

- frozen `CHARTER-1` completion contract と下記追加 gate を通る。
- release note に envelope、budget、failure、assurance limitation を記載。
- clean source、reproducible environment、compact evidence/checksum package。
- no unresolved P0/P1、P2 は documented workaround/typed unknown。
- annotated release tag。

## 5. quantitative gates

### 5.1 frozen CHARTER-1 completion contract

以下は推奨値ではなく、owner agreement なしに弱化できない release contract である。

- frozen family-disjoint blind corpus で `P_full_validated(180 s) >= 95%` overall
- every critical stratum >= 90%
- predeclared exact-eligible corpus で `P_full_exact(180 s) >= 95%`
- false exact、false validated、strict-boundary、wrong-branch、false-completeness outputs = 0
- blind problems の少なくとも 90% が 30 seeds 中 27 seeds 以上で成功
- 420 s result は 180 s verified answer を一つも失わず、180 s misses の少なくとも半数を解く
- family-clustered one-sided 95% confidence bounds を報告し、結果後に gate を緩めない
- primary budgets は fast=60 s、standard=180 s、thorough=420 s
- bounded と adaptive-unbounded results を必ず分けて報告

exact-eligible gate は全 problem を RUR/Gröbner で解く要求ではない。exact capability を事前宣言できる subset に対し、configuration validity と target identity の独立 certificate を要求する。数値 algorithm 開発を先に進めてもよいが、G5 からこの gate を削除してはならない。変更には owner agreement と `CHARTER.md` amendment が必要である。

### 5.2 additional research/promotion gates

以下は CHARTER を置換せず、algorithm selection と safety evidence を補う推奨値である。final campaign 前に固定し、現 baseline の claim としない。

### answer safety

- local lab: reported-accepted canonical-invalid/Gold-inconsistent/numeric-target-only/ambiguous witness = 0
- production: false provisional/validated/exact promotion = 0 on frozen development/holdout controls
- strict guard/domain/branch invalid promotion: 0
- exact/validated false certificate: 0
- metamorphic representation disagreement in promoted answer: 0

zero observed error は descriptive count として報告し、case/family/seed cluster、adversarial coverage、raw denominator を併記する。adaptive endpoints を独立 Bernoulli と見なした `3/N` rule は使わない。明示的に独立 sampling design を別途成立させた audit だけは、その限定された母集団に対する binomial bound を報告してよい。

### all-target reliability

local T0–T2 screening では `P_lab_safe_full_target` を使う。これは全 Gold target が `reported_accepted && gold_matched` witness で覆われ、全 reported-accepted endpoint が canonical/Gold consistent なときだけ成功とする。production release ではこの proxy を使わず、CHARTER の `P_full_validated` / `P_full_exact` を使う。

追加診断:

- family-clustered one-sided 95% lower bound
- close-root/conditioning/opaque strata の point estimate と denominator
- prefix success の非減少
- 60/180/420 s の fixed-target ECDF / ERT

これを満たせない family を平均で隠さず、scoped limitation または typed route として明示する。

### performance

- local screening control に対し、同 lab-safe-full なら total work 20%以上改善、または同 work で lab-safe-full +5 points 以上
- production control に対し、CHARTER reliability を維持して total time/work 20%以上改善を目標
- critical stratum の full-target loss <= 2 points、かつ CHARTER の 90% floor を下回らない
- warm callback gain が compile/sampling/validation を含む end-to-end で消えない
- standard budget の median と tail/ERT を両方報告
- old implementation を再現できる subset では paired speed/recall comparison を行う

「飛躍的高速化」は倍率を先に作らない。compiler-heavy case、local-hard case、multi-root case を分け、各 cost component の実測倍率を示す。

### software quality

- public stable API に experiment knob を漏らさない
- runtime route は public numeric/capability metadata のみ
- one production event loop、one canonical validator、one evidence store
- dead candidate/dependency/branch を削除
- `main` のみを長期 branch とする
- full CI と deterministic replay green
- docs/SDK example と new opaque plugin smoke green

## 6. unknown-problem holdout design

| set | 未知性 | 例 | 何を検証するか |
|---|---|---|---|
| U1 | parameter/seed | known family の未使用 condition/separation | interpolation、threshold overfit |
| U2 | composition | known primitives の新 graph/branch combination | DSL/compiler/local interaction |
| U3 | family | 新 generator/failure mechanism | algorithm generalization |
| U4 | plugin | private type + opaque differentiable operation | black-box/open-world compatibility |

rules:

- candidate freeze 前に manifest/hash を commit。
- assessor truth と algorithm input を分離。
- opening 後に調整した set は holdout ではなくなる。
- failed case を隠さず failure taxonomy と typed status に結び付ける。
- U4 は polynomial lowering、operation-name routing、AD-only requirement を拒否する。

## 7. real geometry corpus

synthetic family だけで release しない。既存/旧 50-case corpus を利用できる場合、次を行う。

1. problem semantics と expected target の independent audit。
2. easy/medium/hard、regular/singular、branch/guard、opaque/plugin に stratify。
3. development と frozen holdout を geometry template 単位で分ける。
4. old solver と new solver を同 machine/budget で paired 実行。
5. solved-only timing でなく unsolved を含む anytime ECDF を報告。
6. case-specific routing を禁止。

old corpus の target/Gold が疑わしい場合は benchmark truth error と solver error を分ける。

## 8. completeness / exactness の user-facing wording

許される例:

> この solver は declared budget 内で探索を継続し、独立 replay を通った target を返します。この実行では全 target を発見したという有限時間の証明はありません。

validated capability がある場合:

> 各表示 target は certified configuration box に由来します。これは各 root の局所 existence/uniqueness evidence であり、未発見 root がないことの証明ではありません。

禁止:

- 「最適化が収束したので正解」
- 「十分時間をかければ必ず全解」— D0 independent capture と fairness の仮定を明示しない場合
- 「BigFloat で residual が小さいので certified」
- 「9 case 中 6 case なので成功率 67%」
- 「全 target」— endpoint scorer が rejected endpoint を含む状態

## 9. release checklist

```text
[ ] OD-01..OD-17 traceability reviewed
[ ] declared envelope and budgets frozen
[ ] control/candidate source and configuration frozen
[ ] assessor/reported metrics and scorer tests green
[ ] U1/U2/U3/U4 holdouts unopened before freeze
[ ] local assessor/reported inconsistencies documented; zero false provisional/validated/exact promotions
[ ] family-equal and critical-stratum thresholds passed
[ ] P_full_validated(180 s) >= 95% overall and every critical stratum >= 90%
[ ] P_full_exact(180 s) >= 95% on predeclared exact-eligible corpus
[ ] at least 90% of blind problems pass 27/30 seeds
[ ] 420 s preserves every 180 s verified answer and solves >= half of 180 s misses
[ ] bounded and adaptive-unbounded reports are separate
[ ] production 30-seed anytime campaign complete
[ ] old/current controls compared at equal budget
[ ] opaque C0 plugin path green
[ ] optional C1/C3V fallback semantics green
[ ] target-collision presentation test green
[ ] full CI + Nightly QA green
[ ] no dead routes/dependencies/long-lived branches
[ ] raw artifacts hashed; compact report reproducible
[ ] limitations and non-completeness language reviewed
[ ] clean main annotated release tag created
```

## 10. 現時点の honest status

- G0: assessor/reported metric と legacy/prod-tol/prod-options control の区別を除き到達。
- G1: 未到達。Trust Region/current LM の current-lab comparison が必要。
- G2: 未到達。現 lab は end-to-end proposal/archive を比較していない。
- G3–G5: 未到達。

したがって repository は「algorithm research-ready」であり、「solver complete」ではない。次 agent は G0 の小修正後すぐ G1 の実験へ入るべきである。
