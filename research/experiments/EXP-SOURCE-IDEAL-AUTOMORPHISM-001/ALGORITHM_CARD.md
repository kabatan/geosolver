# EXP-SOURCE-IDEAL-AUTOMORPHISM-001

## Hypothesis

A rational geometry residual system can have a finite signed-coordinate
automorphism group.  If the ordinary solver has safely reached one member of a
solution orbit, applying an exact source automorphism can cheaply place a new
start in another basin without coefficient continuation or truth knowledge.

## Duplicate audit and pivot

The initially requested `COEFFICIENT_MONODROMY_EQUIVARIANT_ORBIT_START_V1`
was stopped before implementation.  It is the same mathematical mechanism as:

- `EXP-COEFFICIENT-MONODROMY-001`: source root embedded as `P(x)-p=0`,
  discriminant lollipop loops, predictor/Newton tracking, source replay.  Its
  final state was `HOLD_ZERO_REAL_ACTIVATION`; no source-only univariate
  projection/reconstruction reopen evidence was available.
- `local_monodromy_orbit_v1`: singular-germ slice loops and induced witness
  permutation/orbit with source/guard replay.
- evidence-ledger `NEG-003`: naive homotopy/lifting is not reopened without a
  diagnosed applicability predicate and three unrelated positive families.

The replacement mechanism here is discrete exact group action on the source
polynomial/predicate system.  It does not use any path or coefficient
deformation and therefore is not a retuning of either failed monodromy route.

## Mechanism and applicability

1. Parse at most 12 variables, 24 QQ residual polynomials, 64 polynomial
   predicates, and 400 total monomials.
2. Enumerate a bounded source-only set of sign flips and signed coordinate
   transpositions.
3. Admit a transform only when:
   - the residual QQ row space is exactly invariant;
   - `gt`/`ge` predicate orientation and `ne` predicate zero sets are invariant;
   - exact rational source bounds are invariant.
4. Close admitted generators to at most 64 finite group elements and map the
   accepted endpoint.
5. Replay the original and every mapped endpoint through the caller's untouched
   canonical source evaluator.  One mapped replay disagreement fails closed and
   discards the complete side orbit.
6. Preserve the supplied baseline `bytes` object on every applicable,
   inapplicable, exception, and replay-failure path.

Only dimension, rational coefficients, residual/predicate structure, bounds,
and the accepted endpoint are consumed.  Problem IDs, family labels, expected
answers, target values/counts, and solver outcome are unavailable.  The
anonymous signature hashes coefficient-free polynomial shapes, signed cycle
types, and orbit cardinality.

## Generated D0 gate

Three unrelated positive mechanisms have paired negative and near-miss cases:

- an even univariate residual with sign orbit;
- a Vieta-style variable swap;
- a paired/global sign action.

Variable rename/permutation, residual row permutation/scaling, and positive
coordinate scaling are metamorphic checks.  A deliberate compiler/replay
disagreement must produce zero proposals and one fail-closed source-invalid
signal.

## Real activation gate

The root-owned runner is restricted to the frozen anonymous degree-one endpoint
panel and digest-pinned source compiler/semantic compiler/legacy evaluator.  It
requires source variables to equal cover variables and rejects reconstruction
or branch replay obligations.  Original and mapped endpoints use the same full
legacy DSL source/guard/hard-feasibility replay.  Only aggregate stage counts
are emitted outside the repository.

Promotion requires at least three activated sources, at least two anonymous
structural signatures, and zero false/source-invalid/fallback-byte mismatch.
Activation alone makes no correctness, target-release, or completeness claim.

## Reopen/stop rule

Stop on zero/narrow real activation.  Reopen only if a source-only audit shows
at least three anonymous sources in two structural signatures whose exact
symmetry is excluded solely by this conservative row-space test (for example,
a demonstrated nonlinear ideal automorphism with a sound bounded certificate).
Do not loosen replay, guards, bounds, or source custody to manufacture firing.
