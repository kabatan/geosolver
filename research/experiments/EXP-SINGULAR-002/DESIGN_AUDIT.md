# Pre-input design audit

This audit was written before `EXP-SINGULAR-002` had an input generator,
materialized case, Gold artifact, candidate trajectory, or outcome runner.
It records why S5 is a new mechanism rather than an S4 case repair.

## What the frozen result establishes

The authoritative S4 summary records 11/15 eligible recoveries for both the
C2 candidate and the separately coded analytic control.  Both mechanisms
failed the orthogonal representation of the same four latent groups while
promoting the signed-permutation and equivalent-DAG representations.  S4
false promotions and candidate/control disagreements were zero.

Consequently, changing only the finite-difference stencil is not a supported
explanation.  The common rank, stopping, applicability, and evidence model is
also in scope.  Conversely, the 11 successes and zero false promotions are
positive mechanism evidence: the result does not justify discarding all
range/nullspace or projected-Hessian methods.

## Shared representation-sensitive quantities in S4

The frozen candidate's final order/null decision normalizes the discarded
singular value by the leading singular value, but normalizes the last step by
`max(1, ||x||_Inf)`.  Its residual decision uses raw-coordinate infinity norms
of the residual, Jacobian, start, endpoint, and last step.  Both final bounds
are

```text
16 * (normalized_last_step^2 + eps(T)^(2/3)).
```

They do not contain the observed spectral difference between `J_h` and
`J_(h/2)`.  Infinity norms are invariant to signed permutations, but not to a
general orthogonal change of coordinates.  That exactly matches the observed
direction of the frozen metamorphic failure, without asserting that it is the
only cause.

S4 also constructs each trajectory probe as `V_null*c`, where `c` is a
counter-derived coefficient vector in the current SVD basis.  Later audit
transport improved consistency of one physical direction, but it did not make
the trajectory map itself independent of an arbitrary basis.  A new mechanism
therefore cannot merely substitute a different counter.

Finally, S4 throws a generic `trajectory final applicability audit failed`
before attaching the individual failing subdecision document to the unknown
outcome.  The frozen artifact therefore supports the shared-audit diagnosis,
but not a post-hoc threshold retune.  S5 requires every Weyl interval,
projector distance, `K` eigenline interval, `B(v)` interval, signed endpoint,
stop operand, bound, and Boolean subdecision to survive in the raw unknown
artifact.

## Revision A1 after the first root review

The first preregistration proposed using full row rank of the flattened map
`C:Sym^2(N_right)->N_left` and a lifted tensor-model solve.  Root review found
two general defects before any input or outcome existed:

1. full row rank of `C` does not imply that a rank-one contraction supplies an
   invertible paper-style `B(v):N_right->N_left`; and
2. "evaluate every unresolved degenerate eigenspace" is not a finite
   algorithm.

Revision A1 therefore keeps `C` only as a diagnostic.  Static counterexamples
now include a full-row-rank `C` with degenerate `K`, and a full-row-rank `C`
whose every simple `K` eigenline has singular `B(v)`.  Both return unknown.
Neither may be rescued by a threshold or basis choice.

The second root review approved Revision A1 as a finite, covariant
preregistration map consistent with the paper-style `B(v)` step.  The approval
states mathematical coherence only.  It supplies no recovery-rate, safety,
budget, holdout, or product evidence; those claims remain behind the frozen
development and independent-audit gates.

## General replacement

S5 changes all three mathematical objects together:

1. represent variable steps and residuals in declared positive-definite
   metrics and use their Euclidean norms;
2. treat the Jacobian as an uncertain operator using the spectral difference
   of paired radii, Weyl intervals, and null projectors; and
3. form the covariant contraction
   `K_ij=sum_(alpha,k) T_(alpha,i,k)T_(alpha,j,k)`, require its eigenlines to be
   simple beyond paired-radius/precision uncertainty, and gate each finite line
   by Weyl full rank of
   `B(q)_(alpha,j)=sum_i T_(alpha,i,j)q_i`;
4. solve `B(q)delta=-U2'J(x_range)V2*q` for both signs of every robust line,
   require all unscaled canonical endpoints to agree within the frozen
   normalized tolerance, and only then apply one common finite safeguard to
   their covariant barycenter.

`C` alone never enters route acceptance.  Repeated `K` eigenvalues, no robust
`B(q)`, a precision-dependent valid-line set, or line/sign endpoint disagreement
returns typed unknown without a preferred eigenvector or best-residual line.

These quantities transform covariantly under orthogonal charts, signed
permutations, and metric-covariant scaling.  Their applicability predicates do
not reference a case, family, primitive, representation label, generator
parameter, known multiplicity, or Gold result.

## Counterexamples retained as mandatory controls

The study still cannot infer an isolated deflation-one root from a small
residual or apparent convergence.  The development and locked splits retain:

- cubic/quartic and other higher-depth tensor collapse;
- constant- and varying-target manifolds;
- small inconsistent nonroots;
- regular close-root and rank-transition traps;
- invalid branch, guard, domain, precision, and budget exits.

Every such case must remain typed unknown.  Relaxing those controls to recover
an isolated family would be a new experiment, not an S5 tuning round.
