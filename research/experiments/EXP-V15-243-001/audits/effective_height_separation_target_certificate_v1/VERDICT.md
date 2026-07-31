# Effective-height separation target certificate audit

Verdict: **STOP before real census.** The height/separation inequality is a
sound conservative proposal kernel, but its exact-root premises are not
authenticated and generated false zero proposals are accepted.

Audited commit: `01f76f664d283da6bc44c0ddec7eaeb5f4730e88`.
The frozen CPU14 D0 still reports 11/11, zero recorded false accepts, authority
false, and no target release.

## Mathematical kernel

The following derivation is safe, including non-monic coordinate minimal
polynomials and coordinates that are not algebraic integers.

- For a primitive irreducible integer polynomial `q_i`, the absolute
  logarithmic height of a root is bounded by its Mahler measure, and Mahler
  measure is bounded by the coefficient L1 norm `M_i`. The implementation uses
  the looser `h(alpha_i) <= log(M_i)`, which is safe.
- After exact denominator clearing, repeated
  `h(a+b) <= h(a)+h(b)+log(2)` and `h(ab) <= h(a)+h(b)` justify the implemented
  product bound `B`. Multiplying by the positive common denominator is also a
  safe height upper bound.
- The compositum degree is at most the product of coordinate degrees. If a
  nonzero algebraic value has degree at most `D` and height at most `log(B)`,
  the product formula gives the safe separation `abs(beta) >= B**(-D)`.
- Interval evaluation uses exact SymPy rationals for addition, multiplication,
  and nonnegative integer powers. It therefore encloses outward without a
  floating-point rounding assumption. Variable permutation and reversible
  rational target scaling preserve the calculation.
- Primitive/square-free/irreducible checks, unique real isolators, and
  factor-local real-root ordinals are recomputed rather than taken from height
  metadata.

## P0 premise-binding failure

The source-root certificate is accepted from a self-digest plus asserted
Boolean fields. It is not joined to a pinned upstream verifier, immutable
all-bytes proof artifact, source bytes, endpoint bits, obligation ledger, or
lineage artifact. In particular, source equations are never checked here and
the certificate's `truth_used` field is ignored while the output always says
`truth_used=false`.

Likewise, a coordinate fact verifies the self-digest of `serialized_qqbar`,
but never requires its polynomial, isolator, and ordinal to equal the outer
coordinate fields used by the height proof.

Two CPU14 generated adversaries were accepted as `VERIFIED_PROPOSAL` with
`target_polynomial_value_exactly_zero=true`:

1. the source statement requires `x=1`, while the coordinate fact and target
   descriptor use `x=2`; all certificate flags were self-signed true;
2. the outer coordinate fact uses `x=2`, while its bound serialized QQBar
   record uses `x=1`.

Both outputs kept authority false and required later canonical replay, so they
cannot directly release a target. They nevertheless invalidate the claimed
zero-certificate activation and the recorded zero-false-accept premise.

## Reopen gate

- Pin an upstream source-root verifier mechanism and bind its complete proof
  bytes, schema, source bytes, endpoint bits, obligation ledger, lineage, and
  coordinate-fact list by independently checked SHA-256 values.
- Require upstream `truth_used=false`, exact equation/guard/definedness/branch
  replay, and same-root uniqueness; do not accept self-asserted flags alone.
- Require exact canonical equality between each serialized QQBar descriptor
  and the recomputed outer minimal polynomial, isolator, multiplicity, and
  real-root ordinal.
- Add the two adversaries above, source/endpoint mutation, wrong branch, wrong
  ordinal, non-monic coordinates, rational denominators, scale, and permutation
  to the frozen unit gate. Only after zero false accepts may a static real
  census run.

No real corpus, formal scorer, Julia process, or heavy benchmark was executed.
