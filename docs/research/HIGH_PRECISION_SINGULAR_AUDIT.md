# High-Precision and Singular-Path Audit

Status: **audited; safety repair committed; next experiment preregistered**
Date: 2026-07-10
Repair source commit: `07b15b8`  
Integrated main commit: `c7f47a1`

## Outcome

The current C2 path is a high-precision **point semantic replay**, not a root
refinement or root-existence check. Before `07b15b8`, an ill-conditioned
black-box system could therefore turn a small residual at a configuration far
from its unique root into a public `ProvisionalAnswer`. The repair makes the
product path fail closed:

- a nonzero-residual correction is unresolved when the measured relation
  Jacobian is rank deficient;
- every `TARGET_IMAGE_INCONCLUSIVE` candidate remains a diagnostic/refinement
  record and cannot enter the verified store or public answer list; and
- exact-zero residuals, near-singular but measured-full-rank corrections, and
  the existing structurally constant manifold path retain their prior control
  behavior.

The exported `validate_candidate` function still accepts the fixed
counterexample when called directly. Its evidence proves only that the same
point obeyed the canonical point-evaluation policy at C2 precision. It does not
prove that a root exists near the point or bound configuration error. This is a
remaining contract surface, not a reason to weaken the solver-side repair.
`EXP-SINGULAR-001` requires semantic replay and root evidence to become
separate typed artifacts before another promotion path is enabled.

## Audited execution path

| Layer | Current mechanism | What it establishes | Missing evidence |
|---|---|---|---|
| Float64 local solve | Normalized central finite differences, damped LM step from augmented pivoted QR, Float64 SVD rank diagnostic | A relation-residual endpoint and local progress trace | Root existence, forward/configuration error, singular multiplicity |
| Target-image diagnostic | C0 or C2 point samples followed by an explicitly Float64 finite-difference Jacobian and SVD | Non-certifying local rank/nullspace/target-sensitivity evidence | Stable rank under precision/radius changes; an isolation proof |
| Root-correction diagnostic | Truncated SVD correction and first-order target step | A heuristic estimate on retained measured directions | Error in discarded near-null directions; nonlinear remainder bound |
| `validate_candidate` | Re-evaluate unchanged coordinates through the canonical interpreter at C2 when available, otherwise an explicit C0 second pass | Relation/domain/guard/branch/target semantics at that point | Coordinate re-refinement, root existence, forward-error enclosure |
| `_numeric_enclosure` | Point value plus configured/roundoff radius | A reproducible numeric comparison interval | Directed-rounding interval extension over a configuration box |

The distinction is required by the floating-point Newton analysis in
[Higham (2002)](https://doi.org/10.1137/S0895479899359837): residual error,
Jacobian/linear-solve error and update error have different effects, and poor
conditioning can separate residual size from forward accuracy. Adaptive
precision based on conditioning is a useful cost mechanism, but the
[Bates--Hauenstein--Sommese--Wampler method](https://doi.org/10.1137/060658862)
is a path-tracking result and does not by itself certify an arbitrary local
endpoint. Rigorous nonlinear verification instead requires an interval
extension and checked theorem assumptions; see
[Rump (2010)](https://doi.org/10.1017/S096249291000005X).

## Fixed P1 counterexample

The test plugin exposes two numeric-generic C2 black-box relations without
polynomial lowering:

```text
F1(x, y) = x + y
F2(x, y) = x + (1 + 10^-13)y
target(x, y) = x
```

The unique root is `(0, 0)`. At `(1, -1)`, `F1 = 0` and
`|F2| ~= 10^-13`, below the `10^-12` candidate residual tolerance, while the
target error is one. The pre-repair trace was:

| Observation | Value |
|---|---:|
| local status | `LOCAL_CONVERGED` |
| C2 semantic replay | accepted at 256 bits |
| target-image class | `TARGET_IMAGE_INCONCLUSIVE` |
| target-image failure | `TARGET_IMAGE_SINGULAR_LINEARIZATION` |
| measured numerical rank | 1 of 2 |
| old retained-subspace correction | `resolved=true` |
| old estimated normalized/target step | about `2.50e-14` / `2.50e-14` |
| direct replay target enclosure | approximately `[1-1e-12, 1+1e-12]` |

With seed 17 and two search actions, the old public solve path emitted one
provisional target centered near `0.0912472661768817`, although the only target
is zero. After `07b15b8`, the same candidate has correction detail
`rank_deficient_nonzero_residual`, remains in the refinement queue with its
diagnostic target niche, and emits no public answer.

This family is identity-free: production routing sees only dimension,
capability, residuals, measured rank/condition and progress. The regression
also includes a `10^-4` tilt that is near-singular but measured full rank, an
exact-zero residual control, an exact-zero singular feasible-manifold control,
and the pre-existing structurally constant target manifold.

## Existing development evidence

The non-gating `EXP-LOCAL-002` development log contains 7,680 paired local
attempts. These are **local endpoint/Gold diagnostics**, not public
`ProvisionalAnswer` results. Nevertheless they quantify why residual
qualification cannot stand in for forward accuracy.

| Family | Residual-qualified endpoints | Not Gold-matched | Target misses at `1e-6` | Maximum target error |
|---|---:|---:|---:|---:|
| Near-rank-deficient | 904 | 156 | 146 | 0.2738132618 |
| Multi-root warped | 820 | 246 | 65 | 0.0021364638 |
| Tangent circle-line | 960 | 0 | 0 | 1.4460522e-7 |
| Curved chain | 832 | 4 | 4 | 1.3499517e-6 |

The source is
`research/results/EXP-LOCAL-002/development-v0/attempts.csv.gz`, SHA-256
`03f6b08841b6e4647749c65d74a1c6e43624214273e382b3bcd7b62e3d0e4b39`.
No selection decision is made from this reused development split.

## Required separation before promotion

The next implementation must preserve one canonical semantics path while
splitting its evidence roles:

1. `SemanticReplayEvidence` records the existing independent C2/C0 canonical
   point replay. Its result is never sufficient to construct a public answer.
2. `NumericalRootEvidence` records a charged C2 re-refinement trace, stable
   rank/condition observations across precision and stencil changes, a
   configuration-error estimate, a propagated target-error estimate, and an
   independent confirmation run. It is provisional numerical evidence, not a
   rigorous existence proof.
3. `ValidatedRootEvidence` records a C3V interval/Krawczyk-style existence and
   uniqueness certificate when every executed plugin path supplies a sound
   interval extension. Capability absence or a singular interval Jacobian is a
   typed unknown, never a C2 fallback presented as validated evidence.

`TargetImageDiagnostic` remains a router only. No rank cutoff, package return
code, precision agreement, or small residual becomes an answer predicate by
itself. All candidate algorithms continue to consume the open
`EvaluationOracle`; no primitive name, problem identity, polynomial lowering,
or new DSL node is introduced.

## Experiment decision

[`EXP-SINGULAR-001`](../../research/experiments/EXP-SINGULAR-001.json) compares
adaptive-precision LM-QR, rank-revealing subset/CPQR refinement, Broyden and
bordered-nullspace singular lanes, plus a capability-gated C3V Krawczyk lane,
from identical frozen endpoints. The experiment is intentionally local: it
does not change discovery, archive, target deduplication, or exact algebraic
promotion. A variant may be specialized to a diagnosed stratum; no universal
singular rescue is assumed in advance.

## S0/S1 development update

The frozen 72-instance development grid was executed after the harness and
input manifests were committed. This is an advancement gate only: locked
validation is false and no product runner is connected.

| Variant | Phase-A Gold success | Promoted | False promotions | Callbacks | Precision-equivalent work |
|---|---:|---:|---:|---:|---:|
| S0 point replay | 0/48 | 0 | 0 | 144 | 688 |
| S1 adaptive-precision dense LM-QR | 48/48 | 48 | 0 | 5,442 | 26,204 |
| Analytic-Jacobian lower bound | 48/48 | 48 | 0 | 2,616 | 11,367 |

All promoted S1 configuration/target estimates contained Gold, and all twelve
near-rank metamorphic groups agreed. Eight inconsistent nonroots, eight
manifold controls and four C0 cases remained unpromoted. Four double-root
diagnostics exhausted the declared iteration budget and remained unknown;
therefore S1 does not resolve the singular-root objective by itself. The
independent Python analysis reproduced the Julia summary and advanced the
experiment to `S2-AP-CPQR-SUBSET`, not to locked validation or product use.

## Verification performed for the repair

- `julia --project=julia julia/integration/solver_runtests.jl`: green, including
  29/29 singular fail-closed assertions.
- `julia --project=julia julia/integration/target_image_runtests.jl`: green,
  including 39/39 rank/image assertions.
- `julia --project=julia julia/integration/runtests.jl`: green, including the
  complete workspace, protocol differential corpus, checkpoint, CLI, proposal,
  compiler, candidate-validation and target-image suites.

## S2/S3 development boundary

S2 recovered 12/12 target-constant rank-deficient manifolds and rejected every
varying-target manifold and inconsistent nonroot in its frozen development
split. That result remains specialized manifold evidence; it does not establish
configuration isolation.

S3 then compared unchanged S1, restarted multiprecision good-Broyden, and an
independently coded analytic inverse-secant control on 30 new endpoints (ten
metamorphic groups). The 64-iteration limit is one endpoint-wide hard budget,
shared by all primary and perturbation trajectories. The official result was:

| Variant | Eligible Gold | Promoted | Budget exhaustion | False | Callbacks | Precision-equivalent work |
|---|---:|---:|---:|---:|---:|---:|
| S1 adaptive-precision LM-QR | 0/12 | 4 | 0 | 0 | 1,209 | 5,049 |
| S3 restarted good-Broyden | 0/12 | 0 | 12 | 0 | 2,388 | 11,292 |
| S3 analytic inverse-secant control | 0/12 | 0 | 12 | 0 | 1,311 | 6,327 |

Every S3 exhaustion stopped at exactly 64 iterations as typed unknown with no
root evidence. No manifold, inconsistent nonroot, or regular close-root control
was promoted by S3. A deliberately non-gating 80-iteration unit diagnostic
needed 68 iterations on one double-root case and exercised the typed evidence
path, but it cannot relax or replace the registered 64-iteration result.

The S1 baseline also changed its decision under equivalent signed transforms of
the closest regular-root case: one form promoted and two remained unknown. This
metamorphic disagreement independently fails the S3 card. Consequently S3 is
rejected as `EVID-18` / `NEG-012`; no retuning, locked inspection, or product
connection is permitted. A bordered-nullspace S4 study must start from a new
frozen development gate.

That new gate is now frozen in
`research/experiments/EXP-SINGULAR-001/s4-preregistration.json`, before S4 input
materialization. It makes the formerly generic S4 label concrete as a C2
range/nullspace two-step iteration based on Shen--Ypma's stable-nullspace
conditions and Lee--Li--Zhi's projected second-derivative correction. The gate
requires an independently differentiated analytic control, one global
64-iteration ledger, stable singular-value gaps and subspace angles, and zero
promotion on higher-depth singularities, manifolds, nonroots and regular close
roots. This preregistration is not S4 evidence: no S4 development or locked
input has yet been materialized and no product path is connected.
