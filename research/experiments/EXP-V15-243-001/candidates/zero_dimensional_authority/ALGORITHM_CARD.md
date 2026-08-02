# AlgorithmCard: source-exact zero-dimensional authority

## Decision

**PROMOTE after core-owner integration and paired ablation.**

This is a structural pipeline correction, not a search heuristic. When an
unchanged v15 source declares zero continuous variables, `[]` is its only
configuration. The correct path skips multistart, evaluates the construction
and target AST exactly, derives a certified descriptor directly, and uses the
existing numerical lanes only to check implementation parity.

Numeric PSLQ is never exact authority in this lane. This is mandatory: an
earlier prototype falsely recognized generated `pi` as a degree-6 algebraic
number even after ordinary 768/1024-bit confirmation.

## Mechanism

1. Verify the source digest, `task == "solve"`, `variables.names == []`, and
   endpoint `[]`.
2. Conservatively prove from the source AST that each target dependency is
   algebraic. Supported operations are rational/algebraic arithmetic,
   algebraic geometry constructions, and `sin(q*pi)`/`cos(q*pi)` for exact
   rational `q`. Unknown or transcendental operations fail closed.
3. Evaluate every fixed construction with exact rationals and SymPy geometry.
4. Prove every source constraint is exact zero and every supported guard is
   exact true. Decimal source spelling is preserved, so `1e-300` is not
   rounded to tolerance-zero. Guard operands are extracted with
   `ast.get_source_segment`, never `ast.unparse`, so underflow, overflow,
   subnormal, signed literals, and nested arithmetic retain their source
   lexemes. Nested `Assume`/`And`/`Or`/`Not` and Python Boolean operators are
   evaluated through a conservative three-valued exact Boolean IR; an
   unsupported child remains unknown even under `Not`. Unknown geometry
   guards fail closed.
5. Evaluate the target AST exactly. Require a real algebraic scalar.
6. Derive `minpoly` directly, clear denominators, primitive-normalize with
   positive leading coefficient, and require irreducible and square-free.
7. Select the real root using exact symbolic equality/inequalities and emit
   an open rational isolating interval. Rational roots use the exact rational
   value and a deterministic `±10^-100` interval; nonrational roots use exact
   rational root isolation to width below `2^-320`.
8. Separately replay the unchanged source at Float64 and 512/768/1024 bits.
   Require finite, hard-feasible, guard-valid, intrinsic-domain-valid lanes,
   and exact-source-target parity within `2^(-bits/2)`.
9. Ignore all numerical PSLQ, minimal-polynomial, and selected-root fields.
   Any failure emits no descriptor.

The returned authority kind is
`SOURCE_EXACT_SYMBOLIC_MINPOLY_ISOLATOR`, and both the top-level output and
descriptor state `numeric_pslq_used: false`.

## Generality and routing audit

Eligibility and routing use only:

- source bytes and digest;
- declared variable dimension;
- endpoint dimension;
- primitive source AST semantics.

The candidate does not read case id, file name, family, truth, expected target
count, prior outcome, case-specific bounds, or target approximation for
routing. The two corpus ids occur only in offline audit/test artifacts.

This applies to the infinite family of fully specified algebraic v15 sources,
not to a named geometric motif. Unsupported operations are safe false
negatives.

## Failure mechanism addressed

The frozen lower replay accepts `[]`, but champion-v1 adaptive HP contracts
reject empty endpoints before that replay. Champion-v1 therefore stored a safe
empty endpoint for `OMC009(C)` but ended with `NO_TARGET_AUTHORITY` and
`FAILED_AUTHORITY_ARTIFACT_UNAVAILABLE`. There is no numerical search problem
when the dimension is zero.

On the digest-fixed algebraic243 corpus, exactly two sources have zero
variables: `OMC009(C)` and `OMC142(B)`. Both have no constraints or guards.
This inventory is diagnostic only and is not solver routing.

## Soundness counterexamples

The generated family proves fail-closed behavior for:

- direct `pi` and `pi + 1/10**80`;
- `sin(1)` and `acos(0)`;
- unknown target functions;
- irrational circle phase;
- false guard;
- `0 = 1e-300` and `AssumeEq(0, 1e-300)`;
- underflowed `AssumeEq(0, 1e-1000)` and an extreme open-bound endpoint;
- unproved geometry guard;
- positive-dimensional source and nonempty endpoint.

A malicious degree-6 numerical descriptor is also injected in a unit test.
The final output remains the exact source-derived polynomial `x - 25`, proving
that numerical recognition cannot influence the descriptor.

## Validation evidence

`test_candidate.py`:

- 25/25 tests pass;
- actual stored source exact descriptors:
  - `OMC009(C)`: `[29, -81]`, real-root index 0;
  - `OMC142(B)`: `[16, -675]`, real-root index 0;
- generated nonrational algebraic target `sqrt(5)`: `[1, 0, -5]`, root 1;
- false/unsupported inputs fail closed;
- every nonempty endpoint retains the unchanged H1 dispatcher route.

`LIGHT_SMOKE_EVIDENCE.json` runs the real replay backend on 21 generated
sources:

- end-to-end exact positives: 4/4, including a literal rational constant;
- safe non-authority outcomes: 17/17, consisting of 15 invalid or unsupported
  inputs plus exact-certificate-positive extreme-literal and nested-Boolean
  sources whose unchanged numerical replay cannot represent the semantics;
- the separate exact guard probe accepts underflow/overflow/subnormal/signed/
  nested arithmetic with no condition-certificate failures;
- the nested Boolean probe accepts `Assume`/`And`/`Or`/`Not` compositions and
  rejects both a false composition and unknown `Xor` under `Not`;
- false/extra target: 0;
- heavy panel run: false.

Frozen evidence omits wall-clock observations, so rerunning either evidence
script with the same inputs produces byte-identical JSON and stable digests.

`STORED_ZERO_DIMENSIONAL_EXACT_EVIDENCE.json` reuses historical stored replay
artifacts only; it performs no new search or held-out run. Both real sources
pass exact source evaluation and numeric replay parity, while
`numeric_pslq_descriptor_used` is false.

## Expected end-to-end effect

- Restore the known development loss `OMC009(C)` without changing any
  positive-dimensional route.
- Cover `OMC142(B)` by the same dimension-only rule.
- Reduce zero-dimensional execution from a full search budget to exact
  evaluation plus replay; formal timing belongs to the integrated ablation.

The projected champion-v1 development count is 132/145 from 131/145, but this
is not a measured paired ablation. Formal promotion still requires that
ablation and exact finalizer integration.

## Expected safe failures

- A valid algebraic source using an unclassified operation is rejected.
- Nonempty `post_process` is rejected because its exact semantics are not
  implemented here.
- Multi-valued or undefined exact constructions fail during evaluation.
- Missing or mismatching numerical replay fails closed even if exact source
  evaluation succeeded.

These are missing-target failures; no fallback numerical descriptor is
allowed.

## Owned files and integration boundary

- `candidate.py`: exact source authority plus replay parity audit.
- `generated_cases.py`: positive and adversarial generated sources.
- `test_candidate.py`: unit and stored-artifact tests.
- `run_light_smoke.py`: generated real-replay micro-screen.
- `run_stored_exact_audit.py`: deterministic stored-source audit.
- `bridge.py`: diagnostic replay dispatcher only; not exact authority.
- `CORPUS_AUDIT.json`, `LIGHT_SMOKE_EVIDENCE.json`, and
  `STORED_ZERO_DIMENSIONAL_EXACT_EVIDENCE.json`: evidence.

No shared worker, champion, geosolver, scorer, DSL, or dataset file was
modified.

## Implementation digests

Digests are recorded after final lint/test in `IMPLEMENTATION_DIGESTS.json`.
