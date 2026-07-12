# 実験 playbook

## 1. 目的

この playbook は、候補 algorithm を速く捨て、再現する gain だけを production へ進めるための手順である。formal publication protocol ではない。必要な integrity は既存 truth-blind runner、paired starts、budget accounting、clean Git artifact で足りる。

## 2. 現 runner の contract

実験原子は `(problem replay checksum, start index, variant)`。

variant に渡るもの:

- dimension
- lower/upper bounds
- variable/residual scales
- black-box `evaluate_case(case, x)`

variant に渡らないもの:

- family / instance ID
- Gold configurations / targets
- saved-start matrix 全体
- `DirectAnalyticProblem`

runner は callback evaluation を自分で数え、per-attempt `evaluation_limit` を強制する。variant 自己申告 count は監査用であり、primary work ではない。Gold は attempt 後の scorer だけが使う。

local `SolverVariant` は stateless または attempt 開始ごとに完全 reset する。closure が過去 endpoint/start を保持すると local pairing の意味が壊れる。portfolio/archive state は R3 の case-total experiment だけで扱う。

`run_solver_experiment` は複数 variant を扱えるが、現 `benchmarks/solver_lab/run.jl` CLI は Core baseline 1 variant だけを構築する。最初の candidate のために CLI registry を大改造しない。小さい experiment driver から `[control, candidate]` を直接渡す。

## 3. 実験前の必須修正 ALG-LAB-000

現 summary の endpoint-based recall を残したまま、frozen-assessor fields と reported-acceptance fields を追加する。

primary:

- reported-accepted distinct-target recall
- `lab_safe_all_targets`
- reported-accepted canonical-invalid / Gold-inconsistent witness
- reported-accepted numeric-target-only / ambiguous witness
- frozen-assessor qualified target recall / Gold-inconsistent witness
- frozen-assessor all-target / safe-all-target

efficiency:

- suffix-stable evaluations to first lab-safe-full
- capped total evaluations at each prefix
- duplicate accepted configuration / target witnesses

unit fixtures:

1. Gold-match endpoint だが `reported_accepted=false` → endpoint recall yes、accepted recall no。
2. reported-accepted canonical-invalid endpoint → safety failure。
3. reported-accepted Gold-nonmatch endpoint → Gold-inconsistent safety failure。
4. target value は Gold に一致するが configuration と target descriptor が不整合 → numeric-target-only safety failure。
5. rejected Gold-nonmatch endpoint → diagnostic false endpoint だが reported-accepted false は 0。
6. 全 Gold target を正しい attempts が覆っても、別の reported-accepted inconsistent endpoint が一つあれば `lab_safe_all_targets=false`。
7. collision target を複数 configuration が与える → target ID set では一回だけ数える。

frozen assessor は全 variants の endpoint を同じ residual/semantics predicate で採点し、library retcode と adapter `reported_accepted` に依存しない。reported metrics は solver self-report の監査、assessor metrics は globalization の fair endpoint comparison に使う。どちらも production validated/exact answer ではない。

primary assessor predicate は endpoint present + finite/in-bounds/semantics-valid independent replay + scaled residual `<=1e-12`。Gold configuration/target matching は `1e-6`。`assessor_all_targets` と、qualified inconsistent/ambiguous endpoint 0 も要求する `assessor_safe_all_targets` を別 field にする。`sqrt(eps)` / `3.7e-11` は secondary sensitivity で、primary cardを置換しない。

これは新しい experiment infrastructure ではなく、現 scorer の意味を完成させる bug fix である。

同じ小修正で `core_lmqr_variant` の `residual_tolerance` と `initial_damping` を explicit configuration にする。旧 control は 120/600 + `sqrt(eps)` なので `legacy-lab-120x600`、tolerance だけ合わせた control は `prod-tol-120x600` と呼ぶ。nominal production local options の 250/2000 + `1e-12` は `prod-options-250x2000` diagnostic とする。full production root-correction/validation は三者とも含まない。

## 4. tier と budget

| Tier | corpus | starts/prefix | cap | 用途 | 実行条件 |
|---|---|---|---|---|---|
| T0 | NearRank、Tangent、Warped `z1`/`z1²`、Curved | launch 2/4/8 | 600 eval/start | 数分で mechanism kill | 全 candidate |
| T1 | representative 9 cases | launch 2/4/8 | 600 | easy regression と DSL C0 smoke | T0 survivor |
| T2 | 8 family × 6 parameterized instances | launch 8/16/32 | 600 | paired development、family generality | T1 signal 後だけ |
| T2-high | T2 subset | 8/16/32 | 2000 | 過去 result/late convergence の診断 | primary にしない |
| T3 | frozen U1/U2/U3/U4 holdout | local: 32、production: declared time | fixed before run | finalist selection | code/config freeze 後 |
| T4 | production path real corpus | 30 seeds、60/180/420 s | case total | release anytime curve | one finalist |

prefix は launch count であり equal work ではない。variant ごとの実消費 callback 数が違うため、primary comparison は common cumulative oracle-work thresholds の curve/ERT とする。partial attempt を正確に interrupt する必要がある R3 までに case-total ledger を追加する。T0 survivor がない段階で T2 generator/harness を作らない。T3 holdout は候補を選ぶ前に manifest/checksum を固定する。

## 5. pairing と sampling

### local experiments

- variant 間で同じ materialized start を使う。
- prefix は最大長の一つの start matrix の先頭列とし、短い prefix を別生成しない。
- Warped `z1` と `z1²` は同 roots/starts の latent geometry cluster。独立 case として confidence を水増ししない。
- start は一つの instance 内の repeated trial であり、独立 geometry sample と数えない。

### proposal/discovery experiments

- maximal prefix 128 の stream を variant/replicate ごとに一度だけ materialize する。
- deterministic base、scramble method、seed namespace、matrix checksum を保存する。
- independent-uniform D0、current `iid`-labelled counter stream、QMC の「seed」を同じ分布と見なさず、paired latent problem/replicate として比較する。
- QMC block を checkpoint ごとに再生成しない。
- sampling、screening、ordering、archive-distance work を charge する。
- pure Halton/QMC diagnostic comparator は promotion ineligible。promotion-eligible mixture では independent-uniform insurance cadence と maximum service gap を記録する。
- refinement-exhaustion 時にも new proposals が止まらないことを mandatory starvation control にする。
- independent-uniform bounded service と、enqueue 済み各 queue の eventual service を別 fairness invariant とする。

### production experiments

原子は `(case, SolveOptions.seed, budget, variant)`。最終候補だけ 30 seed を使う。27/30 等の raw count と confidence interval を報告し、best seed を選ばない。

## 6. primary metrics

### safety

- `reported_accepted && !canonical_valid`
- reported-accepted false configuration / target
- reported-accepted numeric-target-only / Gold-inconsistent witness
- reported-accepted ambiguous target
- frozen-assessor Gold-inconsistent / invalid endpoint
- strict guard/domain/branch invalid promotion
- exception
- runner cap violation
- runner evaluation count mismatch
- truth leak / case-ID route
- independent-uniform insurance starvation

truth leak、runner cap/count violation、budget-ledger bypass は run invalid、production false provisional/validated/exact promotion は candidate kill であり、平均 score に混ぜない。local frozen-assessor inconsistent endpoint は R1 では control 比 non-increase、R2 acceptance gate 後に reported-accepted inconsistency 0 を要求する。既知 NearRank proxy がある R1 前に assessor inconsistency absolute zero を要求しない。ここで accepted は `reported_accepted` という local self-report であり、production verified answer ではない。

### all-target performance

- reported-accepted distinct-target recall
- frozen-assessor distinct-target recall
- `P_assessor_all_targets`
- `P_assessor_safe_all_targets`
- `P_lab_safe_full_target`
- family-equal `P_lab_safe_full_target`
- critical stratum の最小 lab-safe-full
- configuration recall は診断、target recall を product primary とする

### anytime / work

- runner-counted black-box evaluations
- suffix-stable first lab-safe-full までの cumulative evaluations。後続 prefix が unsafe なら success と数えない
- prefix success curve と area/ERT
- budget exhausted count
- duplicate accepted witness work
- unresolved case を budget-censored とした fixed-target ECDF / capped work

「解けた case だけの平均時間」は使わない。

### timing

- 初期 selection は callback evaluation を primary とする。
- `cold_first_use` と `warm` を分ける。
- variant order/family-specific JIT の影響があるため、warm wall は T0/T1 では diagnostic。
- finalist は fresh process、同一 thread/BLAS、AB/BA order または process replicate で end-to-end time を測る。
- compile、sampling、screening、local、canonical validation を production total に含める。

## 7. decision rule

候補 code を書く前に、一ページの card で threshold を固定する。初期 recommended gate:

### zero-required

- production validator の false promotion = 0
- truth leak = 0
- budget/count violation = 0
- R3 では permanent independent-uniform fairness violation = 0
- R1 globalization は common-assessor inconsistent endpoints を control より増やさない。R2 前に absolute zero を要求しない

### performance path A — recall improvement

- family-equal `P_assessor_all_targets` が control より原則 +5 percentage points 以上
- critical close-root/close-target/conditioning stratum が 2 points 超悪化しない
- callback work が 1.20×以内。大きな recall gain がある場合だけ例外理由を明示

### performance path B — efficiency improvement

- `P_assessor_all_targets` が noninferior、目安 delta >= -1 point
- callback work または production end-to-end wall が 20% 以上減る
- critical stratum が 2 points 超悪化しない

### generality

- T2 では少なくとも 3 unrelated families が同方向、または candidate の applicability predicate で事前定義した stratum 全体で同方向
- family-clustered paired one-sided 95% interval を報告
- one family の大 gain で他 family の loss を隠さない

### simplicity / kill

- 2 tuning rounds 以内に signal がなければ停止
- recall と work がともに control の 5%以内なら extra policy/code を削除
- 別 solver loop、validator、archive copy を必要とするなら停止して既存 seam で再設計

数値 threshold は final campaign 前に owner と freeze する。experiment 後に都合よく変えない。

## 8. 統計集計

1. attempt から instance/prefix metrics を作る。
2. latent geometry 内の target-map replicas を一 cluster とする。
3. instance 内 starts を集約する。
4. family 内 instance を平均する。
5. family を等 weight で集約する。
6. paired variant difference を family-clustered bootstrap する。

既存 `research.harness.bootstrap.family_clustered_paired_bootstrap` の小さい関数を再利用してよい。formal host、authority file、private vault、AppContainer は使わない。

report には point estimate、one-sided 95% bound、各 family の effect、raw denominator を併記する。confidence interval が狭くなるまで start を独立 sample として水増ししない。

## 9. false endpoint の調査手順

1. `reported_converged`、`reported_accepted`、`canonical_valid`、Gold match を分ける。
2. primary assessor tolerance は `1e-12`。`sqrt(eps)` と `3.7e-11` 近傍は事前宣言した secondary sensitivity として再採点する。
3. internal solver tolerance の変更と assessor tolerance の変更を同 experiment で混ぜない。
4. normalized configuration distance、target error、rank/condition、correction norm を見る。
5. small residual / large configuration error は forward-uncertain と分類する。
6. fixed near-null nonroot、regular close-root、exact-zero で false rejection/promotion を確認する。
7. manifold は有限 Gold configuration distance で false candidate とせず、target-image/continuity の別 assessor を使う。

Gold distance は原因分析だけに使う。production route に Gold threshold を書かない。

## 10. 最初の三つの experiment card

### ALG-LAB-001 — damping / Trust Region globalization

control:

- `legacy-lab-120x600` LM-QR（continuity）
- `prod-tol-120x600` LM-QR (`residual_tolerance=1e-12`, `initial_damping=1e-3`) を primary control
- `prod-options-250x2000` は production option sensitivity diagnostic

candidates:

- smaller fixed damping values（diagnostic only）
- external NonlinearSolve LM control
- external NonlinearSolve Trust Region reference
- reference/mechanism survivor 後だけ native bound-aware TR または safeguarded scale-aware LM

external reference の最初の再現は、既に `NonlinearSolve = 4.20.2` と local GeoTarget sources を pin した `research/experiments/EXP-LOCAL-002/Project.toml` + `Manifest.toml` を environment として使う。旧 Gold-aware adapter/harness は呼ばず、新 truth-blind adapter だけを読み込む。実行 project を JSON に記録する。control/candidate は同じ warm-up policy と order balance を使い、T0/T1 wall は diagnostic のままとする。

primary:

- frozen-assessor target recall / Gold-inconsistent endpoints、reported acceptance diagnostics、matched cumulative callback work
- production validator smoke の false promotion 0

ablation:

- same FD/scaling、globalization だけ変更
- external vs native で library-specific effect を分離
- fixed tiny damping は scale sensitivity を反証する control であり default 候補にしない

kill:

- current runner で過去 gain が再現しない
- common-assessor Gold-inconsistent/invalid endpoint が control より増える
- 600 cap で gain がなく 2000 cap だけで現れる
- gain が `1e-16` 等の一つの magic constant と代表 scale だけに依存する

### ALG-LAB-002 — condition-aware correction/acceptance

control:

- ALG-LAB-001 champion

candidates:

- two-stencil CPQR correction
- SVD diagnostic control
- Float64 target-sensitivity/error control
- capability-gated high-precision correction は Float64-only lab/current research strategy を使わず、precision-aware callback + independent work ledger の separate budgeted driver。strategy利用には charged precision seam が先

primary correction thresholds は Gold 非依存で固定する。`τ_x=sqrt(CandidateValidationOptions().residual_tolerance)=1e-6`、`τ_T=CandidateValidationOptions().target_consistency_tolerance=1e-12` とし、validation configuration/hashをcard/JSONへ記録する。threshold sensitivity は別 variant。

primary:

- NearRank/Tangent の assessor inconsistency、reported acceptance recall、unknown/rejection rate、Gold-recoverable false rejectionを別々に報告
- production false promotion 0
- regular controls recall noninferior
- <=20% unrelated overhead

kill:

- 全 endpoint を reject するだけ
- fixed cutoff が representation replica で route disagreement
- point BigFloat replay だけを root evidence とする

separate Stage B:

- canonical-valid endpoint の scaled Jacobianから weak direction/subspace を得る。root/isolation evidenceとは呼ばない。
- normalized `u ± r_k v` を既存 refinement queue へ入れる。
- 同 probe 数の isotropic perturbation を control にする。
- radius grid、両符号、最大 probes/configuration を result 前に固定する。
- representation/manifold/guard/unaligned-close-root counterexamples を含める。
- endpoint correction と discovery proposal の effect を一つの variant に混ぜず、個別 ablation 後にだけ組み合わせる。

### ALG-LAB-003 — discovery stream

control:

- frozen local champion + materialized independent-uniform D0 all-launch

candidates:

- pure Halton diagnostic（単独 promotion 不可）
- current `iid`-labelled counter/Halton mix
- pure Owen-scrambled Sobol diagnostic（単独 promotion 不可）
- 25% independent-uniform + 75% QMC
- independent-uniform + frozen weak-direction refinement（ALG-LAB-002B survivor only）
- start-source champion 後だけ soft novelty/order

primary:

- multi-root full-target success at enforced/matched case-total work。launch prefix を fixed budget と呼ばない
- close-root/collision regression
- sampling/scheduler overhead
- independent-uniform fairness と refinement-exhaustion non-starvation
- enqueue 済み heuristic/refinement queues の eventual service

kill:

- hard suppress / permanent discard
- pure Halton/QMC source を insurance なしで production promotion
- one deterministic prefix だけの gain
- QMC/current counter stream へ D0 IID の probabilistic claim を付ける
- weak-direction probe が same-budget isotropic control に勝たない

## 11. variant 実装 pattern

```julia
candidate = SolverVariant(
    "candidate-v1",
    (case, start) -> begin
        # case metadata and evaluate_case(case, x) only.
        SolverAttemptOutcome(
            endpoint;
            status="...",
            reported_converged=...,
            reported_accepted=...,
            evaluations=reported_count,
            iterations=...,
            diagnostic="...",
        )
    end;
    configuration=(algorithm="...", option=value),
)

run_solver_experiment(
    problems,
    [core_lmqr_variant(), candidate];
    prefixes=(2, 4, 8),
    evaluation_limit=600,
)
```

configuration は algorithm の全 knob を JSON へ残す。variant 名だけで意味を推測させない。local runner は attempt ごとに state を reset し、過去 attempt を closure state に残さない。

proposal/archive experiment はこの per-start callable に無理に押し込まない。proposal source は `UnstableResearchStrategy` + `solve_execution` で full production path に通せるが、現 seam は scheduler lane weights と CandidateStore を置換しない。それらの survivor 仮説には既存 component 上の最小 research seam が別途必要である。

## 12. experiment card の一ページ template

```markdown
# ALG-LAB-NNN: title

Owner directives: OD-01, OD-03, OD-05, OD-06, OD-15
Baseline revision/artifact:
Failure observation:
Hypothesis:
Control:
Candidate and single changed mechanism:
Primary/official source and source-to-code trace:
Reference / GeoTarget-adapted / mechanism-off control:
Minimum-success and mechanism-activation fixtures:
Runtime-visible inputs:
Cases / latent clusters:
Prefixes / budgets / seeds:
Primary safety metrics:
Primary recall/work metrics:
Kill gate:
Promotion gate:
Maximum tuning rounds: 2
Raw artifact path and SHA-256:
Result:
Cause classification: invalid run / implementation defect / unexercised /
  applicability limited / budget-parameter limited / bounded negative /
  inconclusive / advance
Independent causal audit:
Decision: repair / retain diagnostic with reopen gate / bounded reject / advance
Code removed or promoted:
```

結果を書くまでは `Result` 以下を空にする。card のために新 schema を作らない。

## 13. Git / commit discipline

通常は `main` 上の小 commit と annotated tag を使う。

推奨 commit sequence:

1. `fix(benchmarks): separate assessor and reported solver metrics`
2. `feat(benchmarks): expose explicit LM control parameters`
3. clean HEAD で control baseline を再生成し、metric schema/options を確認
4. `research(alg): preregister ALG-LAB-001 comparison`
5. `feat(research): add truth-blind TR reference variant`
6. clean HEAD で T0/T1 run
7. `research(alg): record ALG-LAB-001 T1 decision`
8. performance 不振なら independent causal-closure commit、advance なら T2 card update
9. bounded mechanism negative と確定した場合だけ candidate/dependency を削除する cleanup commit

harness change と solver mechanism change を同 commit にしない。gating run は clean HEAD で行う。

parallel work:

- agent A: literature/assumptions、reference conformance、read-only
- agent B: candidate implementation + minimum-success/activation tests
- agent C: scorer/analysis と outcome 後の independent causal review
- root: integration、run、decision

同 file の同時 edit は避ける。短命 branch/worktree が必要なら `codex/alg-lab-001-*` とし、統合後削除する。

## 14. artifact policy

raw:

```text
benchmarks/results/raw/ALG-LAB-001/<git-short-sha>/...
```

tracked:

- one-page card/decision
- aggregate table JSON または Markdown
- raw SHA-256
- Git HEAD/dirty
- variant configuration
- problem replay checksums
- Julia version/thread/machine

tracked しない:

- 巨大 attempt traces
- copied manifests/dependency trees for rejected variants
- formal receipts/authority files
- unreviewed plots only

## 15. test ladder

candidate edit 中:

```powershell
julia +1.12.6 --startup-file=no --history-file=no `
  --project=julia `
  -e 'using Test, GeoTargetBenchmarks, GeoTargetCore, JSON3; const REPOSITORY_ROOT = normpath(pwd()); include("julia/integration/solver_lab_runtests.jl")'

julia +1.12.6 --startup-file=no --history-file=no `
  --project=julia julia/integration/local_solver_runtests.jl
```

runner/scorer change:

```powershell
julia +1.12.6 --startup-file=no --history-file=no `
  --project=julia/GeoTargetBenchmarks `
  -e "using Pkg; Pkg.instantiate(); Pkg.test()"
```

T2 survivor:

```powershell
powershell -File scripts/ci.ps1 -Tier Smoke
```

production champion:

```powershell
powershell -File scripts/ci.ps1
```

## 16. rollback

- candidate は control の public default を直接上書きせず、research variant として始める。
- performance gate 不通過だけでは code を削除しない。source/official conformance、
  mechanism activation、applicability、budget/parameter、measurement を独立監査する。
- bounded mechanism negative の場合だけ code/dependency/knob を削除し、decision、
  causal classification、source/raw hash、counterexample を残す。
- implementation defect は新 version で修復し、unexercised/applicability-limited/
  inconclusive は family rejection にせず reopen gate を残す。
- production integration は一 commit に閉じ、直前 tag へ容易に戻せるようにする。
- public result schema/DSL/plugin ABI を変更する candidate は停止し、owner へ design decision を提示する。
- `EXP-LOCAL-003` formal/AppContainer はこの playbook の依存ではない。
