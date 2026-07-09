# GeoTarget Project Charter

Status: **frozen for v1**  
Contract version: `CHARTER-1`  
Changed only with explicit owner agreement.

## Mission

For a deterministic finite-dimensional real geometry model, recover every
distinct final scalar target value as reliably and quickly as possible within a
fixed wall-clock budget. GeoTarget enumerates target values, not necessarily all
geometric configurations.

## Product invariants

1. **Numerical-first.** Discovery is based on numerical optimization/root
   solving over black-box construction programs. Full Gröbner/RUR computation
   is neither a normal path nor an automatic fallback.
2. **Open geometry language.** A plugin-qualified typed call may contain
   differentiable or locally Lipschitz Julia code, custom objects, iteration,
   control flow, transcendental functions and multi-valued constructions.
   Polynomial lowering is optional optimization, never a requirement.
3. **Truth is canonical.** Surrogate, lifted, deflated or continuation views may
   propose candidates, but final residual, domain, guard, branch and target
   checks always use the canonical construction semantics.
4. **No false certainty.** Search exhaustion is `unknown`, never proof of no
   solution. `certified_empty` or `complete_certified` requires an external
   coverage certificate. A numerical recognition is not an exact proof.
5. **Two answer levels.** `ExactAnswer` requires configuration validity and a
   separate proof of the target's algebraic identity. `ProvisionalAnswer`
   requires independent high-precision or validated numerical rechecking.
   Unverified candidates are diagnostics, not answers.
6. **Safety before recall.** False exact answers, false validated answers,
   invalid strict-boundary limits, wrong branches and false completeness claims
   are release-blocking.
7. **Anytime and fair.** Verified results are prefix-monotone across longer
   budgets. An independent full-support lane, finite-branch fairness, archive
   fairness and unbounded-shell dovetailing may not be starved by heuristics.
8. **General mechanisms only.** Production routing may use dimension, scale,
   capabilities, evaluation cost, residual/guard statistics, rank/condition,
   branch margins and progress. It may not use case IDs, file names, primitive
   names, known answers or magic target tables.
9. **One implementation of each truth-bearing mechanism.** There is one
   reference semantic interpreter, one event loop, one candidate store, one
   evidence log and one final verification pipeline.
10. **Experiment before promotion.** Search algorithms are not fixed by this
    charter. Every nontrivial production policy change must cite a preregistered
    experiment and pass the promotion gates.

## Scope of v1

Included:

- finite, discrete real scalar target images;
- smooth, piecewise-smooth and declared nonsmooth deterministic primitives;
- bounded domains and separately evaluated adaptive-unbounded domains;
- Float64 discovery, derivative routing, BigFloat refinement, validated
  numerical checks and algebraic exact proofs when plugin capabilities allow;
- Julia API, JSON CLI and Python authoring layer.

Excluded from the v1 completion claim:

- general theorem proving or general nonexistence proofs;
- complete enumeration of arbitrary complex solution sets;
- nondeterministic or arbitrarily discontinuous callbacks;
- mandatory symbolic elimination of the whole coordinate system;
- a geometry construction UI.

When the target varies along a feasible manifold, GeoTarget reports a likely
continuous image instead of presenting a finite list as complete.

## Completion contract

The frozen, family-disjoint blind corpus and exact-eligible corpus must satisfy:

- `P_full_validated(180 s) >= 95%` overall;
- at least `90%` in every critical stratum;
- `P_full_exact(180 s) >= 95%` on predeclared exact-eligible problems;
- zero false exact, false validated, strict-boundary, wrong-branch and false
  completeness outputs;
- at least 90% of blind problems succeed in 27 of 30 seeds;
- the 420 s result never loses a verified 180 s answer and solves at least half
  of the remaining 180 s misses;
- family-clustered one-sided 95% confidence bounds are reported and gates are
  not relaxed after observing results.

The primary budgets are `fast=60 s`, `standard=180 s`, and `thorough=420 s`.
Bounded and adaptive-unbounded results are always reported separately.

## Conditional asymptotic claim

Under explicitly documented assumptions—finitely many target values, finite
branches, deterministic evaluation, a positive-measure capture basin (or a
positive-probability lane) for every isolated answer, and fair progress of all
scheduled work—the probability of discovering and validating all targets is a
design goal that tends to one as runtime tends to infinity. This is not a
finite-time completeness claim.

## Decisions requiring owner agreement

- weakening completion gates or shrinking the tested envelope;
- changing Exact/Provisional semantics;
- a destructive public ABI/schema change after v1 freeze;
- changing locked benchmark partitions after results are observed;
- introducing case-specific production logic or an RUR/Gröbner fallback;
- configuring/pushing a remote, publishing artifacts, or selecting a license.

