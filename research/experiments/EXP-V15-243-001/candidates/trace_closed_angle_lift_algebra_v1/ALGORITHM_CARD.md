# TRACE_CLOSED_ANGLE_LIFT_ALGEBRA_V1 — D0 preregistration

## Decision scope

```text
projective complex Angle product: GENERATED_D0_ONLY
source compiler / solver integration: NOT_IMPLEMENTED
formal authority / target release: NEVER_IN_THIS_PROTOTYPE
real development, validation, sealed: FORBIDDEN_AND_NOT_RUN
```

## Hypothesis and exact mechanism

For each typed direct unsigned `Angle(u,v)`, a source-proved orientation
`epsilon in {-1,+1}` selects

`z = dot(u,v) + i * epsilon * cross(u,v)`.

The strict obligation `epsilon*cross(u,v) > 0` makes `arg(z)` exactly the
original principal unsigned Angle in `(0,pi)`.  For a rational relation

`sum(q_j * Angle_j) = q_pi * pi`,

the compiler clears all denominators once.  Positive integer exponents use
`z^n`; negative exponents use `conj(z)^(-n)`, avoiding division because the
discarded norm factor is strictly positive.  The product proposes two exact
conditions: its imaginary part is zero, and `(-1)^m * real(product) > 0` for
the cleared integer target `m`.

This cover forgets multiples of `2*pi`.  A mandatory winding ledger propagates
the source-proved rational principal ranges and accepts only when the sole
integer compatible with `sum(n_j theta_j) = (m+2k)pi` is `k=0`.  Zero or
multiple possible windings fail closed.  The generated D0 replay then
re-evaluates the supplied typed vectors with exact principal `atan2`; the
product equations are not consulted by that second evaluation.

This second evaluation is not production canonical replay.  `canonical_dag`
is only an opaque generated label here, and neither immutable source bytes nor
source AST ordinals are bound.  Integration must independently parse immutable
source bytes, bind source SHA + relation-root ordinal/node SHA + compiler SHA,
resolve both direct-Angle operands, and invoke the pinned canonical
source/guard/definedness/branch/raw-target replay.

## Frozen novelty boundary

The excluded prior mechanism is commit `f536cc99`, connector
`typed_semantic_equal_qbar_pi_affine_v1/sector_angle_connector.py`.  Its closed
shape has one direct Angle on each equality side, each optionally multiplied
by a positive integer in `1..3`, with no sum/difference within a side, pi term,
offset, fractional coefficient, or nested scale.  `is_legacy_sector3_shape`
conservatively excludes the normalized family; such input raises
`LEGACY_SECTOR3_SHAPE_EXCLUDED` and contributes zero activation and zero
positive examples here.  Exact real-corpus subtraction must call the frozen
syntactic scanner on the original DAG before normalization, because canceled
or nested syntax may normalize into this family even though the old scanner
would reject it.

This D0 instead exercises three-or-more-Angle sums, rational coefficients
after denominator clearing, negative coefficients, orientation/reflection,
and explicit winding failures.  No old source ID, source payload, generated
shape, expected answer, score, or outcome is used.

## Authority and fallback

Every `PhaseCover`, proposal check, and generated replay reports
`authority_pass=false` and `target_release=false`.  The executable is only a
mechanism test.  Production use would still require the pinned source compiler,
a certified source root, untouched canonical source/guard/branch/raw-target
replay, and the repository descriptor authority.  Any unsupported expression,
undecided exact sign, wrong orientation, boundary, alias, ambiguity, resource
cap, or exception returns the exact untouched baseline object.

Fixed general caps are 8 Angle atoms, rational denominator 24, coefficient
numerator 64 bits, denominator LCM 10,000, absolute cleared exponent 12,
total exponent mass 24, absolute target integer 64, 2,000 compiled operations,
and 32,768 expression characters.  Floats and booleans are rejected.  Winding
bounds use exact analytic ceil/floor arithmetic rather than target-sized
enumeration.  These are not case-specific routing features.

## Generated D0 gate

CPU14-only generated execution is preregistered for:

- triangle angle sum;
- a three-Angle rational sum/difference with denominator clearing;
- reflection with the orientation ledger flipped;
- undefined collinear vectors;
- a modulo-cover-valid `2*pi` alias;
- a principal-range winding ambiguity;
- all term permutations;
- an exact algebraic near miss;
- explicit rejection of the frozen legacy Sector 3 shape.

The gate requires every positive proposal and generated exact Angle
second-evaluation to pass, every negative to fail closed, permutation digest equality,
reflection cover equality, legacy activation/positive counts zero, and false
authority/release counts zero.  No real source compiler, formal worker, or
development/validation/sealed corpus may run at D0.

## Frozen D0 result and independent audit

```text
pytest:                         9/9 passed
positive proposal + replay:    3/3
negative controls:             5/5 rejected
term permutations:             6/6, one normalized digest
reflection:                    1/1 algebraic-cover invariant
legacy activation / positive:  0 / 0
false authority / release:     0 / 0
decision:                      HOLD_SOURCE_BINDING
```

The independent audit passed the algebraic mathematics: denominator clearing,
conjugate handling for negative exponents, pi parity, signed interval
propagation, and strict collinear rejection.  Its resource and ledger findings
were repaired before freeze: coefficients/targets are capped, winding integers
are derived analytically, and `check_exact_proposal` replays every principal
range exactly.  The remaining P1 is architectural and explicit: the D0 replay
shares candidate-owned typed atoms and therefore cannot authenticate original
source bytes.  No source census or integration claim is promoted from this
artifact.

```text
candidate.py SHA256:        3658acc82d516218d2aa33b6820cbb459e121b6f37f631e5db18c79907d8c03c
GENERATED_RESULT.json SHA:  729b2eb721281608647b4d71dc5f6a8d8dc2bc0afe23e1bf01b29eec40d118a9
```

## Reopen gate

The only reopen is an immutable-source binding plus the pinned production
canonical replay described above.  Only after that repair may a truth-blind
source-syntax prevalence census explicitly subtract every legacy Sector 3
relation accepted by the frozen scanner.  Real integration additionally
requires at least two unrelated multi-Angle/rational/offset signatures.
