# Small exact-polynomial coefficient monodromy D0

Status: `GENERATED_D0_PASS; PROPOSALS_ONLY; NO_REAL_ADAPTER`.

- Candidate SHA-256: `60e1019ed384744fc8209169066b327d742ab84e5293c2de0729c03c7131631d`.
- Runner SHA-256: `1242b8d7024644179ad36e7f61c11fe3dcdc943076a91ede3e7d697a63429ee0`.
- Aggregate SHA-256: `71fd71311c37a7b2d38b82eafaafb1d1621ee06a880798fd310aea520cc31cb0`.

## Mechanism

The candidate admits only an exact-rational, square-free, univariate source
block of degree 2 through 8 with bounded coefficient size. Given one
source-replayed root, it embeds the source as `P(x)-p=0`. Roots of `P'` provide
coefficient-space discriminant values. Fixed lollipop loops around those
values are tracked by complex predictor/Newton correction and may return on a
different sheet at `p=0`.

Every return point is a proposal only. The generated assessor independently
factors the untouched exact source polynomial, reapplies strict source bounds,
and emits a rational descriptor only after exact Horner replay. Complex,
out-of-bound, repeated-root, malformed, nonfinite, and budget-exhausted paths
fail closed. Numerical monodromy never claims root or target completeness.

The first 75% of charged work is an identical baseline. Candidate and control
both spend the remaining 25%; unused tracker budget becomes evaluation filler
with no proposal authority. Candidate output is a union with the retained
baseline descriptor.

## Generated D0

The panel has 160 cases: separated, affine-scaled, and close rational roots;
strict-bound, repeated-root, and real-plus-complex-sheet counters; degrees
2/4/6 and ten replicates.

- Complete sets: `50 -> 130`.
- Descriptor gain/loss: `+220/-0`; strict gains in 80 cases and all 3 positive
  families.
- False/extra and charged-work mismatch: 0.
- Canonical replay rejected 110 complex or strict-bound proposals.
- Repeated-root applicability: `0/30`, as required.
- Nonzero rational equation-scale metamorphics: `90/90`.

No formal truth, scorer, case outcome, development score, validation, sealed,
or holdout input was read. The generated exact factorer is verifier-only and
is not imported by the candidate.

## Next gate

Before any real screen, perform a source-only capability census for an
already-existing exact polynomial projection. Do not build a compiler. A thin
adapter may proceed only when it can provide exact rational coefficients, a
square-free certificate, source bounds, and an already canonical-replayed
start root, while retaining at least 75% common-control work. Every proposal
must return through the existing canonical source replay. Stop if fewer than
three anonymous source structures qualify, if compilation/path overhead
exceeds the 25% route budget, or if any control descriptor is lost.
