# EXP-TRIG-LIFT-D0-001: operator-safe trigonometric algebraic proposals

## Decision

```text
tiny typed recognizer + algebraic side solver handoff: GO_TO_TRUTH_BLIND_STATIC_CONNECTION_AUDIT
generic source compiler: HOLD
shared solver integration: HOLD
real development run: NOT_RUN
validation/sealed: FORBIDDEN_AND_NOT_RUN
standalone authority: NEVER; canonical source replay is mandatory
```

This D0 establishes only that an explicit same-phase sine/cosine construction
can be lowered to a finite algebraic proposal problem, inverted to every
bounded source sheet and filtered safely. It does not establish real-corpus
recall or speed.

## Hypothesis and reopen gate

The strict whole-source polynomial lanes reported zero direct applicability
because the source representation remained transcendental. The hypothesis is
that *operator metadata*, rather than a general expression compiler, can expose
a small polynomial block without changing the source semantics.

This is not a reopen of generic polynomialization. The owner-directed reopen
gate is narrower: the archived semantic lift already implements the unit-circle
cover and replay ledger, but explicitly did not connect or run a joint root
backend. This candidate tests only that missing handoff:

```text
typed explicit pair -> c,s cover -> tiny algebraic proposal solver
                    -> atan2 + finite sheet ledger -> canonical source replay
```

Stop if a truth-blind static adapter cannot supply at least three structurally
independent source-native blocks, if canonical replay does not accept any new
proposal, or if the lane consumes more than its 25% portfolio quota.

## Archive overlap audit

Audit was completed before implementation over the experiment archive with
`half-angle|stereographic|atan2|semantic algebraic lift|PointOnCircle` searches.

- `semantic_algebraic_lift` is a **direct overlap** for phase recognition,
  `c^2+s^2=1`, finite `atan2` sheet ledgers and mandatory replay. Current file
  hashes are card `e9720256...ba1d`, compiler `4ab15c79...9836`, replay
  `8c1c18e4...d23a`. Its card says the frontend is `HOLD`, the real run is
  `NOT_RUN`, and it “does not run a joint polynomial solver”. Operator lowering
  itself is therefore not claimed as novel here.
- `point_on_circle_periodic_semantics` repairs the periodic source-domain
  contract; it is a required semantic neighbor, not an algebraic root solver.
- `periodic_local_metric` changes local topology/metrics and does not lower
  operators.
- `certified_polynomial_lane` reports `0/243` direct applicability without the
  semantic cover; `eligible_polynomial_homotopy_revisit` likewise records the
  strict classifier failure. Those negative results motivate the narrow
  representation reopen but are not evidence of improved recall.
- No archived candidate hit implemented a half-angle/stereographic root
  generator. The missing pole in that chart is handled explicitly in this D0.

## Mechanism and safety boundary

`PhaseSpec` must come from existing typed operator metadata. Both operands must
have exactly equal variable, rational multiplier, rational offset, unit,
operator and phase ID:

- radians accept only explicit `SinCos` metadata and use
  `phi = a*theta + pi*b`;
- turns accept only `PointOnCircle` metadata and use
  `phi = 2*pi*(a*theta+b)`;
- mixed units, nonlinear/raw scalar escapes, absent pair members, nonfinite
  bounds and excessive sheet counts fall back immediately.

The side solver substitutes

```text
c = (1-u^2)/(1+u^2), s = 2u/(1+u^2)
```

into at most four degree-six polynomials. This enforces `c^2+s^2=1`. It solves
one finite univariate numerator numerically, checks every original lifted
equation, and separately checks the omitted pole `(-1,0)`. Degree, equation and
sheet caps are fixed general resource gates.

Each lifted point is mapped by `atan2(s,c)` to every source sheet admitted by
the finite bounds. The bound prefilter is deliberately inclusive. A proposal
is released only if a fresh external replay explicitly returns all of:

- canonical source replay performed;
- strict guards valid;
- branch valid;
- ordinal valid;
- safe with source residual at most `1e-7`.

Exceptions, absent replay fields and invalid residuals reject the proposal.
The baseline owns at least `ceil(0.75 * slots)` slots in every portfolio.

## Optional sound Distance lowering

The D0 also tests one small second stage because existing operator metadata can
prove the needed sign. `Distance == positive literal` and
`Distance == Distance` are squared only when every nonliteral operand is typed
`Distance` with proved nonnegativity. The emitted equation is respectively
`D^2-k^2=0` or `D1^2-D2^2=0`. Negative literals, unknown sign, `sqrt`, `abs` and
arbitrary expressions fail closed; no branch is inferred or discarded.

This is a helper over already supplied squared-distance polynomials, not a
geometry/source compiler.

## D0 generated evidence

Python 3.12.11, NumPy 2.5.1 and SciPy 1.18.0 were used in one process pinned to
CPU 15. No scorer, expected answer, real case or holdout was read.

```text
tests:                 26/26 pass (0.04 s reported by pytest)
positive families:      6/6 emit replay-accepted proposals
negative families:      5/5 emit none or fall back
near-miss families:     6/6 emit none or fall back
ruff:                    clean
baseline quota:          75% minimum
```

Positive coverage includes radian quadrants, a PointOnCircle antipodal pole,
multiple harmonic sheets, a nonlinear polynomial on the circle, a proved
Distance-to-literal square and a negative multiplier with rational phase
offset. Negative and near-miss coverage includes mixed units, raw-angle escape,
an inconsistent polynomial, a positive-dimensional circle identity, untyped
operators, a strict endpoint, branch/ordinal/residual vetoes, a sheet-cap
overflow and an incomplete pair.

## Expected failures and next gate

- Multiple independent phase groups, non-affine phases and variables escaping
  into ordinary scalar arithmetic remain baseline-only.
- Numerical polynomial roots can miss ill-conditioned/multiple roots. This is
  proposal recall loss, not unsound acceptance, because canonical replay is
  mandatory. Do not tune chart tolerances per case.
- A unit-circle algebraic cover can contain points not representing the
  required source sheet or selector. Replay is the authority for all such
  distinctions.
- Positive-dimensional systems and resource-cap overflow stay with the
  numerical baseline.
- Root values are not exact certificates and this D0 bypasses neither exact
  finalization nor canonical source replay.

The next permitted action is a truth-blind static adapter/census owned by the
benchmark owner, followed by generated source-native connection tests. Formal
145/243 scoring remains out of scope for the candidate owner.

## Artifact hashes

```text
candidate.py         0b4d808dfefe20e61cc4ff79f7f37fa64f29d227744fb93a8c28e804921e55a9
generated_cases.py   e2cc0236f6001f62f6ce0eb1121179ffd9df11e30afba8d6b77b6400809dda06
test_candidate.py    103eae2beed1849a46c64e77fd9c4904b49c53000fcc280142cb7c50db10351f
```
