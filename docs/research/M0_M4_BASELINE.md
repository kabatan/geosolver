# M0-M4 Numerical Research Baseline

Status: **preregistered control specification**
Baseline ID: `RB0-IID-LMQR-1`

This baseline exists to make compiler, local-solver and discovery experiments
comparable. It is deliberately smaller than the v1 product scope and is not a
claim that the final GeoTarget algorithm has been selected.

## Research envelope

For M0-M4 promotion decisions, the baseline covers deterministic bounded real
problems with:

- 1-16 free variables;
- 1-64 residuals;
- 1-1024 construction nodes;
- one real scalar target;
- a branch-free graph or a branch whose selector margin is separated from a
  tie;
- Float64 evaluation (C0), with derivatives optional (C1); and
- reference roots at least 0.05 normalized units from an artificial search-box
  boundary for the primary gate.

Strict-boundary, selector-tie, singular-manifold and adaptive-unbounded cases
remain diagnostic during M0-M4. This is a staging restriction, not a reduction
of the frozen v1 scope.

## Control pipeline

`RB0-IID-LMQR-1` performs the following steps.

1. Type-check the construction graph and build a nested `EvaluationOracle`.
2. Generate a serial block of IID uniform starts over the bounded box.
3. Run every start with raw variables and raw residuals through a
   QR-based Levenberg-Marquardt adapter.
4. Re-evaluate every endpoint with the canonical oracle.
5. Append every attempt and every accepted internal candidate to the single
   EvidenceLog. No target cluster suppresses a later start.
6. Repeat until the deadline or launch budget is exhausted.

The initial research settings are a batch size of 32, local `maxiters=250`,
and prefix checkpoints after 8, 16, 32, 64 and 128 local launches. These are H0
hypotheses and may change only through a card's declared tuning procedure.

The nonlinear adapter sets `abstol=reltol=eps(T)^(4/5)` and treats a point as
an internal discovery candidate only when canonical evaluation is finite,
domain/guard/branch checks pass, and the infinity norm of the scaled residual
is at most `sqrt(eps(Float64))`. A library success return code alone is never
enough. NonlinearSolve documents the same type-dependent default termination
scale and exposes explicit iteration/time controls in its
[official solve interface](https://docs.sciml.ai/NonlinearSolve/stable/basics/solve/).

M0-M4 candidates are diagnostics, not `ExactAnswer` or `ProvisionalAnswer`
objects. Public assurance levels are introduced only when their independent
verification paths exist.

## Evidence and budget contract

Each local attempt records:

- problem, graph, plugin, policy and environment hashes;
- proposal lane, seed block, start index and start coordinates or their replay
  artifact;
- endpoint, raw/scaled residuals, target, guards, branch and evaluation status;
- local return code, canonical acceptance decision and first failure ID;
- primal, Jacobian/JVP/VJP and high-precision evaluation counts;
- compile, calibration, screening, local and canonical-validation wall time;
- rank/condition diagnostics and termination reason.

The research harness starts with one Julia thread and one BLAS thread. Parallel
scheduling is added only after deterministic traces are established. Julia's
standard library warns that seeded streams may change between minor releases;
therefore exact replay locks the Julia/Manifest versions and stores proposal
artifacts or checksums rather than relying on a seed alone
([official Random documentation](https://docs.julialang.org/en/v1/stdlib/Random/)).

Search exhaustion is `unknown` or `budget_exhausted`, never `no_solution`.

## Full-support invariant

Let a finite target set have IID capture probabilities `p_i > 0` under the
fixed local solver. After `N` independent starts,

```text
P(miss any target) <= sum_i (1 - p_i)^N
                   <= K exp(-N p_min).
```

Consequently the permanent insurance lane must satisfy
`N_independent(t) -> infinity`. Heuristic ordering may change finite-budget
performance but may not starve this lane. For future adaptive-unbounded work,
the shell schedule must also revisit every finite shell infinitely often. This
is a conditional asymptotic design claim, not a finite-time completeness
certificate.

## Milestone ordering

1. **M0:** schemas, manifests, truth policy, literature matrix and experiment
   cards validate.
2. **M1:** a new reference interpreter and analytic synthetic generators define
   semantics independently of the retired implementation.
3. **M2:** `EXP-COMP-001` selects a compiled-oracle strategy or retains the
   typed-plan control.
4. **M3:** the single event loop and `RB0-IID-LMQR-1` produce deterministic,
   replayable traces.
5. **M4:** The terminal `EXP-LOCAL-001` pilot is diagnostic only and freezes no
   champion. The prospective `EXP-DISC-001-A3` dependency chain first completes
   or terminally closes `EXP-LOCAL-003` and freezes its locked-passing scaling
   policy or explicit `L0-SEMANTIC`. It then preregisters and runs the separate
   current-core native-globalization study `EXP-LOCAL-004` with that frozen
   scaling policy. After `EXP-LOCAL-004` terminates, an outcome-bound record
   freezes exactly one complete local pipeline. A missing locked scaling pass
   falls back to `L0-SEMANTIC`; a missing locked globalization pass falls back
   to current LM-QR while retaining any independently locked-passing scaling
   policy. Neither stage may fall back to a non-gating pilot.
6. **M4 discovery gate:** `EXP-DISC-001` may materialize candidate/assessor
   inputs or proposal matrices only after that record binds the original card,
   A1, A2, A3, the exact champion source, canonical options, ABI/compiler and
   environment hashes. Every discovery policy is then compared with that same
   immutable local pipeline.

The old implementation may provide a hypothesis or timing reference, but it is
never a Gold oracle, imported runtime dependency or source of accepted truth.
