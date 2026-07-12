# EXP-DISC-001 — Global basin emitter research queue

Status: pre-outcome algorithm research note  
Date: 2026-07-12  
Scope: bounded black-box multi-root discovery  
Production connection: none

This note freezes two candidate mechanisms and their controls before any Stage C
ordering outcome is used. It is not a preregistration, efficacy result, promotion
decision, completeness claim, or authorization to materialize inputs.

## Research question

If reordering a fixed start set cannot change its terminal answer set, can a bounded,
truth-blind emitter generate points in previously unvisited root basins at lower
case-total callback work than fresh IID alone?

The runtime mechanism may use only finite bounds, dimension, public numerical
capabilities, canonical validity, scaled residuals, branch observations and charged
progress. It may not use case, family, file or primitive names, Gold targets, known
roots, or target identities.

## Primary and official sources

- DIRECT: Jones, Perttunen and Stuckman, “Lipschitzian optimization without the
  Lipschitz constant,” 1993: <https://doi.org/10.1007/BF00941892>
- SciPy official DIRECT interface and implementation notes:
  <https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.direct.html>
- SHGO: Endres, Sandrock and Focke, “A simplicial homology algorithm for Lipschitz
  optimisation,” 2018: <https://doi.org/10.1007/s10898-018-0645-y>
- SciPy official SHGO interface and implementation notes:
  <https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.shgo.html>
- Topographical initialization for constrained nonlinear systems:
  <https://doi.org/10.1016/j.apnum.2016.10.007>
- APOSMM: Larson and Wild, “Asynchronously parallel optimization solver for finding
  multiple minima”: <https://doi.org/10.1007/s12532-017-0131-4>
- libEnsemble official APOSMM documentation:
  <https://libensemble.readthedocs.io/en/release-v_1.1.0/examples/aposmm.html>
- MLSL Part I and II: <https://doi.org/10.1007/BF02592070> and
  <https://doi.org/10.1007/BF02592071>
- NLopt official MLSL documentation:
  <https://nlopt.readthedocs.io/en/stable/NLopt_Algorithms/#mlsl-multi-level-single-linkage>

## Common truth-blind adapter

For a point `x`, let `z = relation_residual(x) / declared_row_scale` and compute a
stable row-permutation-invariant two-norm `rho = ||z||_2`.

Use the bounded scalar score

```text
rho <= 1: phi = rho / (1 + rho)
rho >  1: phi = 1 - 1 / (1 + rho)
invalid, nonfinite, guard/domain failure: phi = 1
```

Thus finite canonical-valid evidence lies in `[0, 1)`, while invalid evidence is
typed at `1`. The score is proposal evidence only. It does not accept an answer,
merge configurations, suppress a target, or certify a root or empty region.

Every objective evaluation requested by an emitter is charged as one screening
callback. Every authorized emitter point, including invalid points and exact
duplicates, is later passed to the frozen local solver and canonical assessor.
External optimizer results, success codes, minima and stopping claims are ignored.

## Full-support insurance and accounting

- A nonzero independent-uniform lane remains permanent.
- At least one IID start is launched in every four discovery launches.
- IID and emitter points use disjoint, frozen seed namespaces.
- If an emitter cannot fill its service slots, fresh IID fills them.
- Enqueued points are never hard-discarded, irreversibly clustered or target-merged.
- A fixed run uses the same number of prescores and local-attempt slots as its control.
- Primary work is observed case-total callbacks: prescores plus whole local attempts.
- `600/1200/2400/4800` callback checkpoints remain the initial comparison grid.
- Wall time includes emitter construction but is secondary during T0.
- External `maxfun` or `maxev` is not budget authority; a wrapper counter is.
- External workers and the solver worker count remain one per case process.

## Candidate A — DIRECT-RECT-EMIT

### General mechanism

Normalize the finite box to a unit cube. Run original, globally oriented DIRECT
(`locally_biased=false`) on `phi`. Record the ordered sequence of evaluated rectangle
centers. The external minimum is ignored; recorded centers are proposals.

DIRECT balances rectangle diameter and center score over implicit Lipschitz constants.
Unlike an ordering-only policy, subdivision generates points not present in D0.

### Applicability

- Every variable has finite, nondegenerate bounds.
- The box passes the frozen normalization-resolution gate.
- The initial stencil fits the screening budget: `1 + 2d <= B_emit`.
- The objective callback can return a typed canonical-valid or invalid observation.

Branch discontinuities, guards and invalid regions invalidate smooth/Lipschitz theorem
transfer. The mechanism remains a measured heuristic there; all sampled invalid centers
are retained and launched.

### Required control — RECT-BREADTH-FIRST

Use the same unit-box ternary rectangle geometry, screening count and proposal slots,
but split rectangles by largest diameter and immutable FIFO ties without reading `phi`.

DIRECT-RECT-EMIT must beat both this geometry-only control and prescored D0. Otherwise
any gain is attributable to stratified subdivision rather than objective guidance.

### Predefined counterexamples

- A thin basin rotated away from coordinate axes.
- A narrow valid island surrounded by an invalid guard/domain moat.
- Close roots sharing one low-residual valley.
- A positive-residual local minimum or flat plateau.
- A constant-target or varying-target zero manifold.
- Several configurations mapping to one target.
- High dimension where axis subdivision diffuses the budget.
- Signed-permutation or tie-order replicas.

### Kill gates

- Any truth leak, false answer, unsafe endpoint or external-result acceptance.
- Any emitted point is omitted, mutated or hard-suppressed.
- IID service gap exceeds four.
- Screening, reported/observed callback or hard-cap accounting disagrees.
- The score-guided candidate does not beat RECT-BREADTH-FIRST at equal work.
- Improvement is confined to one named case or one family.
- No same-work terminal new-target signal outside MultiRoot/Tangent.
- Scale, signed-permutation or equivalent-DAG replicas change the answer class.
- Orthogonal replicas expose unacceptable axis dependence.
- Construction overhead exceeds the preregistered unrelated-family ceiling.

## Candidate B — SIMPLICIAL-STAR-EMIT

### General mechanism

Use SHGO-style simplicial sampling to construct a bounded normalized complex. Evaluate
all base vertices with `phi`. Identify branch-compatible combinatorial local-minimum
vertices from complex adjacency. In round-robin order across minima, emit interior
points between a minimum vertex and barycenters of its incident simplices.

All evaluated base vertices and generated star points are proposals. No external local
minimum, homology rank or SHGO success state is answer authority. This is an
SHGO-inspired GeoTarget emitter, not a claim that the full SHGO theorem transfers.

### Applicability

- Finite, nondegenerate, normalization-resolved box.
- The initial complex fits the screen budget: `2^d + 1 <= B_emit`.
- Simplices and adjacency fit a fixed memory cap before evaluation.
- Canonical validity and opaque branch equality are publicly observable.

The dimensional/budget condition is capability-based, not case-based. Inapplicable
slots fall back to IID and are excluded from efficacy denominators but remain in safety
accounting.

Invalid vertices stay in the complex, receive score `1`, and are launched. Homology or
finite sampling is never used to infer root absence, isolation or completeness.

### Required control — SIMPLICIAL-UNGUIDED

Use identical base vertices, complex, number of interior proposals and callback work,
but select simplex interior points in immutable geometry-only FIFO order. The guided
candidate must beat this control and prescored D0; otherwise topology did not add value.

### Predefined counterexamples

- A basin wholly inside a simplex while all its vertices have high score.
- Thin diagonal basins sensitive to triangulation phase.
- A disconnected valid island whose surrounding vertices are invalid.
- Flat or tied residual labels producing unstable minimum stars.
- Several topological minima converging to the same target.
- Exponential `2^d` growth and simplex-memory growth.
- Equivalent triangulation and vertex-order replicas.

### Kill gates

- Any common safety, truth, IID-service or callback-accounting violation.
- Initial vertices or simplex storage exceed the predeclared cap.
- A generated/evaluated vertex or star point is not serviced.
- The guided candidate does not beat SIMPLICIAL-UNGUIDED at equal work.
- Improvement occurs only in dimension two or one family.
- No terminal new-target signal outside MultiRoot/Tangent.
- Signed-permutation, scale or equivalent-DAG replicas change the answer class.
- Triangulation bookkeeping is larger than the candidate algorithmic benefit warrants.

## Why TGO, APOSMM and MLSL are later in the queue

TGO selects local starts from an already sampled k-nearest-neighbor topograph. The
current Stage C wave directly tests this order/defer mechanism. Without generating new
points, another TGO adapter cannot change the fully drained terminal start set.

APOSMM coordinates local runs using better-neighbor distances and information from all
evaluated sample and local points. It is a strong later candidate for reversible launch
eligibility and asynchronous budget allocation, but it needs a global source and changes
local-run coordination as well as proposal generation.

MLSL combines random or low-discrepancy samples with clustering that avoids repeated
local searches. Hard cluster suppression conflicts with close-root insurance. Removing
that suppression reduces its immediate role to a source plus soft ordering already
covered by Stage A and Stage C.

These methods are not rejected. They remain queued for reversible scheduling after a
genuine point-generating emitter and the frozen local solver have been evaluated
separately.
