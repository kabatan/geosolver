# Hermite Repair A — digest-pinned typed source seam

## Scope

Repair A fills only the narrow seam between an existing ordinary square-free
target descriptor and the D0 Hermite witness. It does not add a geometry
primitive, alter either shared compiler, infer a bound, or use endpoint
proximity as routing.

The candidate loads these existing files read-only and refuses a digest change:

- `EXP-REAL61-002/algebraic_lane/compiler.py`:
  `f127f7f1...b10318`;
- `semantic_algebraic_lift/semantic_lift.py`:
  `4ab15c79...99836`;
- current exact_outer worker: `05650c10...d3f7`;
- current exact_outer authority boundary: `a36520a4...67e9`.

The direct-exact eligibility aggregate previously reported 0/243, including
126 non-polynomial, 83 unavailable-symbolic, and 17 timeout failures. Repair A
does not reopen or extend that exporter. The semantic auxiliary evidence was
also only static and lacked exact source authority. Those are constraints on
scope, not activation estimates for this candidate.

## Lossless accepted subset

Both pinned compilers independently process the untouched source. Repair A
accepts only when:

- the algebraic compiler returns `EXACT_SEMIALGEBRAIC`, with no reconstruction
  or non-canonical replay obligation;
- the semantic lift is proof-ready and has exactly one raw-target replay link;
- neither side has phase, Boolean-selector, or definedness obligations;
- their variable rings, equation multisets, and typed-predicate multisets are
  exactly equal over QQ;
- the ordinary descriptor is well typed, square-free, has one root in its open
  rational interval, and its global real-root ordinal matches the interval.

Every typed predicate is transformed mechanically:

- `g > 0` becomes a strict Hermite/Tarski guard;
- `g < 0` becomes `-g > 0`;
- `g >= 0` or `g <= 0` introduces an existential square slack;
- `g != 0` introduces an exact inverse equation;
- `g == 0` becomes an equation.

The raw target link, `p(t)`, and both open interval legs are included in the D0
problem. The exact certificate is checked by the independent multiplication-
matrix verifier. A fresh pass then re-reads the same source bytes, checks their
SHA, reloads both pinned compilers under fresh module names, rebuilds the
binding, and verifies the same certificate again. No coordinate is exactified.

## Exact_outer dry OR seam

`exact_outer_or_route.py` is an additive generated/dry seam for the ordinary
exact_outer route. A successful Repair A proof may return the already-proposed
descriptor. Every inapplicable or failed repair calls the supplied existing
fallback unchanged; non-ordinary and zero-dimensional route kinds bypass the
repair entirely. Baseline quota and existing fallback logic are not modified.

## Explicit fail-closed boundary

The two compiler implementations use different auxiliary naming and replay
models for radicals, quotients, periodic sheets, and geometric selectors.
Building a general correspondence would be a new semantic compiler. Repair A
therefore rejects definedness, phase-sheet, and Boolean-selector ledgers rather
than dropping them. This keeps the seam below the `STOP_SEAM_COST` boundary.

## Generated gate

Three anonymous strata activate target degrees 1, 2, and 4. Together they
exercise `ge`, `gt`, and `ne`. Each is repeated under a source-variable rename
and invertible affine target transform. Negative controls cover wrong strict
sign, descriptor/source mismatch, strict boundary zero, and the three explicit
unsupported ledgers.

Result: 9/9 positive variants accepted and replayed; 6/6 controls rejected;
false accepts 0. Maximum observed quotient dimension was 4, maximum polynomial
term count 5, and maximum total term count across all D0 input polynomials 18.
Configured caps remain quotient dimension 32, 256 terms per polynomial, and
1,024 aggregate adapter terms.

The adversarial Boolean `Or` input that formerly surfaced an `AttributeError`
now becomes explicit `NOT_PROVED` in D0. Repair A additionally catches every
non-system exception at both the adapter and OR boundaries. An expired dry
deadline emits no descriptor or partial certificate. The deadline check is
cooperative, however; there is no hard-kill child-process contract in Repair A,
so formal authority remains HOLD.
