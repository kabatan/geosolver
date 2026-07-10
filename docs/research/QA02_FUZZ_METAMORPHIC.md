# QA-02 deterministic fuzz and metamorphic gate

QA-02 is implemented by `julia/qa/QA02Fuzz.jl` and the process-boundary
runner `julia/qa/run_qa02.jl`.  It is a deterministic safety gate, not an
algorithm-selection experiment and not a source of routing features.

## Frozen generators

- Generator version: `1.0.0`
- Graph seed namespace: `5855013983061426512`
- Solve seed namespace: `5855013983262559318`
- C2 evaluation precision: 256 bits
- Nightly minimum: 10,000 graph evaluations and 1,000 bounded solve
  executions

Each case seed is derived independently with a frozen SplitMix64 mapping.  The
generator owns its `MersenneTwister`; it does not use the process default RNG.
It selects numeric coefficients and graph data only.  All plugin kernels are
fixed, reviewed functions declared by a test-only `PluginSpec`; generated input
never contains executable code, primitive names used for product routing, or
locked benchmark truth.

## Graph differential and metamorphic coverage

One counted graph evaluation means one generated, validated graph evaluated at
one input and capability by both the reference interpreter and compiled oracle.
Their full semantic projections (status, target, relation raw/scaled/truth,
guards, domains, branch decisions and charged logical work) must agree.

The Nightly matrix comprises 500 independently generated graph pairs, ten
dyadic inputs per pair, and both the base and transformed graph at each input:

- 5,000 C0/Float64 and 5,000 C2/BigFloat differential evaluations;
- scalar, plugin-owned opaque-object and finite-branch/selector families;
- valid and invalid domain/guard observations without plugin failure or
  capability fallback;
- topological reordering of independent nodes;
- equivalent nested affine graph form;
- duplicate immutable constants and constant calls that exercise CSE;
- provably inert literals that exercise safe DCE;
- positive relation-residual scaling with matching scale metadata;
- redundant equivalent relations;
- stable-key branch selection after candidate-order reversal; and
- a declared nonzero affine target map checked against the base target.

The transformed residual set must preserve scaled residual and truth semantics,
and the transformed target must equal its declared affine image.  Feature
coverage is counted in the canonical summary, so removing a generated family or
metamorphism changes the checksum and/or fails an explicit invariant.

## Bounded solve and checkpoint coverage

Every solve cycle makes four public `solve_execution` calls: uninterrupted,
same-seed replay, a one-action prefix, and a decoded-checkpoint resume of the
remaining action.  Thus the frozen 1,000-execution gate contains 250 independent
cycles and 250 canonical checkpoint resumes.

Generated analytic cases are balanced over:

- a feasible one-variable linear root with an affine target;
- the same isolated root rejected by a strict guard;
- the same isolated root rejected by a separately declared domain;
- a continuous unconstrained target image, for which no finite public answer is
  allowed; and
- an exact dyadic literal target with no variables.

For every returned `ExactAnswer`, the approximation must match a generated
analytic target.  For every `ProvisionalAnswer`, its enclosure must contain a
generated analytic target.  Cases with no isolated feasible target must return
no public answer.  Missing answers are not converted into false-answer success;
the safety gate specifically requires zero false public answers.

The runner additionally checks:

- byte-stable same-seed evidence replay;
- prefix/resume equivalence of public result, workspace, budget and event trace;
- canonical checkpoint encode/decode/encode identity;
- monotone budget events, configured ceilings and public coverage consistency;
- absence of callback/protocol terminal failures;
- no consumption of the process-default RNG (checked against a copied control
  state, then restored); and
- restoration of ambient `BigFloat` precision after each cycle.

Deadlock resistance is bounded by the public wall budget and finite action
prefix in each process.  Nightly also runs the same reduced stable projection in
two fresh processes: one Julia thread at ambient precision 96 and two Julia
threads at ambient precision 384.  Their core checksums must match.  Keeping
this check at a process boundary prevents the precision test itself from
polluting the main fuzz process.

## CI tiers and reproduction

`scripts/ci.ps1` runs small deterministic prefixes in Smoke and PR, and freezes
the required counts in Nightly:

```powershell
# Local PR-sized prefix (all three graph families and all five solve truths)
julia +1.12.6 --startup-file=no --history-file=no --project=julia `
  julia/qa/run_qa02.jl --graph-evaluations 60 --solve-executions 20 --skip-isolation

# Complete Nightly gate
julia +1.12.6 --startup-file=no --history-file=no --project=julia `
  julia/qa/run_qa02.jl --graph-evaluations 10000 --solve-executions 1000 `
  --require-nightly-minimum
```

The runner emits canonical JSON and a checksum over deterministic fields.
`--require-nightly-minimum` rejects a lowered requested count; every run also
fails if completed counts differ from requested counts.  `--output PATH` writes
the same canonical summary for CI artifact collection.

## 2026-07-10 local rehearsal

The full-count deterministic core gate completed on Windows/Julia 1.12.6 in
649.583 seconds (678.6 seconds process wall time):

- graph differential mismatches: 0 / 10,000;
- C0/C2 split: 5,000 / 5,000;
- metamorphic pairs: 5,000;
- solve executions/checkpoint resumes: 1,000 / 250;
- false public answers: 0;
- replay/prefix failures: 0;
- RNG/precision interference failures: 0; and
- run checksum:
  `sha256:69ecd3ac3ea924da9ad525fd4174bc6c1a89d749009ed7eda74108444ccdb0b1`.

The canonical result is retained at
`research/results/QA-02/nightly-rehearsal-v1.json`.  A separate process-isolation
rehearsal (40 graph evaluations and 8 solve executions per child) completed for
both thread/precision environments with checksum
`sha256:23da0c4fc7a2d127132b566989f440329d6b5201e3c33f937ca19e7fcc3898dc`.
The exact replay commands, process and suite wall times, child thread counts,
ambient precisions and matching checksums are retained beside it in
`research/results/QA-02/rehearsal-metadata-v1.json`.
The full-count and isolation components were therefore exercised locally; CI
Nightly composes them in one invocation.

This evidence closes the implemented QA-02 count gate.  It does not claim
locked-family recall, multi-week soak, multi-process search, or release
certification; those remain separate completion gates.
