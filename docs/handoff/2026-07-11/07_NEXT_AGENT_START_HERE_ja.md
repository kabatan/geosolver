# Next agent: start here

## 0. 目標

最初の cycle の成果物は「新しい framework」ではなく、次の四つである。

1. frozen-assessor / reported-acceptance を分離した current baseline
2. `legacy-lab-120x600`、`prod-tol-120x600`、`prod-options-250x2000` の明示的 control
3. Trust Region / damping-globalization の paired T0/T1 result
4. native candidate を作るか止めるかの短い decision

## 1. 作業開始時

```powershell
cd C:\solver
git status --short --branch
git rev-parse HEAD
git tag --points-at HEAD
powershell -File scripts/doctor.ps1
```

期待:

- branch `main`
- HEAD は `solver-handoff-2026-07-11` が指す本 handoff commit またはその直後
- algorithm-ready ancestor `e2cf389`
- clean tree
- remote なし

baseline artifact があることを確認:

```powershell
Get-FileHash benchmarks/results/raw/solver-lab-baseline.json -Algorithm SHA256
```

旧 hash は `B495F81FDA8376C28017123D9DCD78D733057E7BC2040F37E50E472D111F7817`。一致しなければ上書きせず別名で保存し、Git/options/environment を確認する。

## 2. Commit 1 — ALG-LAB-000 scorer fix

主な edit:

- `julia/GeoTargetBenchmarks/src/solver_experiment.jl`
- `julia/GeoTargetBenchmarks/test/runtests.jl`
- 必要なら `julia/integration/solver_lab_runtests.jl`

追加する metric:

- reported-accepted target set / recall
- `lab_safe_all_targets`
- reported-accepted canonical-invalid / Gold-inconsistent
- reported-accepted numeric-target-only / ambiguous
- `assessor_qualified` / target recall / Gold-inconsistent
- `assessor_all_targets` / `assessor_safe_all_targets`
- evaluations to first lab-safe-full

守るもの:

- 現 endpoint metrics は diagnostic として残す。
- variant API を変えない。
- Gold は scorer 内だけ。
- evaluation accounting を変えない。
- schema change は field addition に必要な最小限。
- `lab_safe_all_targets` は全 Gold target の accepted consistent witness に加え、全 reported-accepted endpoint の canonical/Gold consistency を要求する。
- `reported_accepted` は local self-report であり production validated promotion ではないと field docs に明記する。
- primary `assessor_qualified` は independent replay、finite/in-bounds/semantics-valid、scaled residual `<=1e-12`。configuration/target match は `1e-6` とし、JSON/cardに固定する。
- `assessor_safe_all_targets` は assessor-qualified consistent witnesses が全 target を覆い、qualified Gold-inconsistent/ambiguous endpoint が 0 のときだけ true。

test:

```powershell
julia +1.12.6 --startup-file=no --history-file=no `
  --project=julia/GeoTargetBenchmarks `
  -e "using Pkg; Pkg.instantiate(); Pkg.test()"

julia +1.12.6 --startup-file=no --history-file=no `
  --project=julia `
  -e 'using Test, GeoTargetBenchmarks, GeoTargetCore, JSON3; const REPOSITORY_ROOT = normpath(pwd()); include("julia/integration/solver_lab_runtests.jl")'
```

commit example:

```text
fix(benchmarks): score accepted solver answers separately
```

## 3. Commit 2 — local control を parameterize

現 `core_lmqr_variant` は `LocalSolveOptions` の default residual tolerance `sqrt(eps(Float64))` を使う。一方 production `SolveOptions` は candidate validation default `1e-12` を local tolerance へ渡す。旧 baseline は production output と同一ではない。

`CoreBaseline.jl` に少なくとも次を explicit keyword として追加する。

- `residual_tolerance`
- `initial_damping`
- 必要なら `finite_difference_step`

variant manifest の configuration に必ず記録する。CLI を拡張する場合もこの 2–3 options だけにし、general option registry を作らない。

三つの control を区別する。

- `legacy-lab-120x600`: residual `sqrt(eps)`、過去 artifact continuity 用
- `prod-tol-120x600`: residual `1e-12`、tolerance effect 用
- `prod-options-250x2000`: nominal production local option sensitivity 用

いずれも root correction、target-image analysis、full canonical product path を含まないため「production solver equivalent」とは呼ばない。

tests:

- configuration JSON に tolerance/damping が入る。
- candidate へ実際に option が渡る。
- default policy hash/public wire protocol は変わらない。

commit example:

```text
feat(benchmarks): expose explicit LM control parameters
```

## 4. Clean HEAD baseline regeneration

reported/assessor fields を含む三 control の paired runner を小 driver で実行する。既存 CLI を一 control のまま残してもよい。

保存例:

```text
benchmarks/results/raw/ALG-LAB-000/<short-head>/representative.json
```

report:

- endpoint assessor recall と reported-accepted recall の差
- legacy vs prod-tol vs prod-options の差
- NearRank/Tangent/Warped の assessor inconsistency、reported rejection/acceptance
- callback work

旧 baseline artifact は削除せず handoff ZIP の reference とする。

## 5. Commit 3 — ALG-LAB-001 card

`docs/research/ALG-LAB-001.md` 一枚だけを作る。記載内容:

- Owner directives: OD-01, OD-03, OD-04, OD-05, OD-06, OD-15, OD-16
- control: `prod-tol-120x600` LM-QR、`prod-options-250x2000` diagnostic
- candidates: external LM、external Trust Region
- diagnostic controls: fixed initial damping values
- T0/T1 case、600 eval/start、launch-count 2/4/8、common cumulative-work thresholds
- common-assessor recall/inconsistency、reported acceptance diagnostics、production-validator safety gate
- maximum tuning rounds 2
- native implementation は external signal 後だけ

固定微小 damping は algorithm champion ではなく mechanism probe とする。問題 scale に依存せず `1e-16` 等を default にするのは避け、gain が出た場合は Moré-style scaling/safeguarded damping または Trust Region radius として一般化する。

commit example:

```text
research(alg): preregister damping and trust-region comparison
```

## 6. Commit 4 — external Trust Region reference

最小 experiment-only adapter を実装する。

- `evaluate_case` callback だけを使う。
- NonlinearSolve の success code を final truth としない。
- runner の per-attempt cap を超えない。
- return endpoint と reported status/count を `SolverAttemptOutcome` にする。
- external dependency は experiment-local。Core dependency へ昇格しない。
- old `EXP-LOCAL-002` の `_external_attempt(problem, ...)` を直接呼ばない。Gold/private problem を閉じる危険がある。
- environment は既存の `research/experiments/EXP-LOCAL-002/Project.toml` + `Manifest.toml` を使い、pin 済み `NonlinearSolve = 4.20.2` で歴史的 signal を再現する。新 adapter だけを読み込む。
- library retcode、adapter `reported_accepted`、frozen assessor qualification を別 field にし、globalization primary は common assessor を使う。

control/candidate を同じ process/warm-up policy と order balance で実行する。T0/T1 wall は diagnostic、callback work を primary とする。

focused control command の例:

```powershell
julia +1.12.6 --startup-file=no --history-file=no --project=julia `
  benchmarks/solver_lab/run.jl `
  --families=TANGENT-CIRCLE-LINE,MULTIROOT-WARPED `
  --prefixes=2,4,8 `
  --output=benchmarks/results/raw/alg-lab-001-control-smoke.json
```

作成後の external driver は次の形で実行する。

```powershell
julia +1.12.6 --startup-file=no --history-file=no `
  --project=research/experiments/EXP-LOCAL-002 `
  benchmarks/solver_lab/experiments/ALG-LAB-001/run_reference.jl `
  --output=benchmarks/results/raw/ALG-LAB-001/reference.json
```

この path は driver 実装時に作る予定名であり、現 handoff 時点では未作成である。

experiment driver は output path、revision、variant config を JSON に残す。

## 7. ALG-LAB-001 の decision

### external TR が勝たない場合

- native TR を作らない。
- 600 vs 2000 cap、legacy vs prod-tol/prod-options の interaction を一回だけ診断。
- 過去 EXP-LOCAL-002 signal が adapter/budget/current-code のどれで消えたかを書く。
- candidate/dependency を削除し、次の failure hypothesis を選ぶ。

### external TR が勝つ場合

- native TR を `SolverVariant` として作る。
- first version は current FD/scaling/QR を共有し、globalization だけ変更。
- external/reference/native の三者比較。
- T1 gate 後にだけ T2 parameter grid を作る。
- T2 survivor を `UnstableResearchStrategy` で opaque plugin production smoke へ通す。
- R2 correction experiment 前に public default を変更しない。

## 8. subagent の割当例

4 concurrent slots の場合:

- root: integration、clean run、final decision
- agent A: NonlinearSolve Trust Region adapter + targeted tests
- agent B: assessor/reported scorer/test、root と file ownership を分ける
- agent C: primary-source assumptions、result JSON independent audit

agent C には、result を見ずに gate/checklist を review させる。実験後は同 agent または別 agent が truth leak、budget count、accepted metrics を再計算する。

## 9. 最初の cycle でやらないこと

- `EXP-LOCAL-003` の formal C0/C1/C2 launch
- AppContainer/ACL 修正
- Rust rewrite
- full compiler rewrite
- general lifted factor graph
- deflation
- homotopy
- singular S3/S4 の再実装
- candidate store 全 redesign
- branch/plugin schema の拡張
- T0 signal 前の 48-case harness 建設

## 10. オーナーへの最初の報告

次を一画面で報告する。

1. prod-tol/prod-options LM control の assessor/reported recall / work
2. external TR の同値
3. NearRank、Tangent、Warped の case-level effect
4. assessor inconsistency、reported acceptance、production-validator false promotion の有無
5. warm/end-to-end overhead の注意
6. native TR に進むか、別仮説へ進むか
7. code/dependency の増減

algorithm 名ではなく、同 budget でどの failure class が何件改善したかを先に示す。

## 11. first-cycle definition of done

```text
[ ] assessor/reported scorer merged and tested
[ ] legacy vs prod-tol vs prod-options controls explicit
[ ] clean paired baseline artifact + checksum
[ ] ALG-LAB-001 card committed before result
[ ] external TR adapter truth-blind and budget-counted
[ ] T0 and T1 result generated
[ ] independent result audit complete
[ ] decision committed
[ ] rejected code removed or native next stage authorized
[ ] main clean; no long-lived experiment branch
```
