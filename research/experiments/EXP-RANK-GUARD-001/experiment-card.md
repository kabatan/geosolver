# EXP-RANK-GUARD-001 experiment card

Status: **S0 complete; charted proposal arm bound for S1, adapted CPQR
fail-closed at the frozen Python seam**.

## Hypotheses

- The frozen `EXP-LOCAL-015` adapted CPQR signal can be recovered by fixing
  aggregation conformance without changing candidate mechanics.
- A callback-bound weak right-singular line can generate symmetric starts with
  exact callback accounting and no representation-dependent proposal count.
- A finite-bound logit chart can increase useful residual-decreasing proposals
  while preserving strict interior bounds and the canonical validation boundary.

## Result

- Zero-count precision bucket normalization removed all 2,625 historical false
  precision mismatches.  Candidate-local representation gating makes adapted
  CPQR conformant: 144/1,008 valid refinement seeds, 270 unsupported seeds,
  zero safety emissions, zero proposal disagreements, and one route/work-only
  disagreement.  This is a positive mechanism signal, not production evidence.
- Weak bracket and weak-then-adaptive remain representation-limited.  The
  successor does not conceal their 11 proposal and 18 route disagreements.
- On the 18 generated case / 72 trial-per-arm S0, direct and charted weak-pair
  arms had zero precision mismatches, zero proposal-count representation
  disagreements, and zero answer/refinement-seed safety emissions.  The charted
  arm produced 69 residual-improving starts versus 42 direct at equal 120
  callbacks.  Six safety-control trials activated each proposal arm; those
  outputs remain unpromoted starts and must pass the unchanged canonical path.

## Disposition

- Advance the charted weak-pair start generator to benchmark-owner S1 as a
  separately hash-bound arm.  This commit does not run or score screen24.
- Do not advance adapted CPQR through the current Python proposal seam.  That
  seam exposes only the charged Float64 source callback; it exposes no
  hash-bound 128/256/512-bit callback with which to reproduce the S0 stability
  certificate.  The arm therefore delegates the frozen champion unchanged and
  writes an explicit blocker into its dry plan instead of substituting a
  Float64 surrogate.
- Do not advance weak-then-adaptive unchanged.  Reopen it only with a stable
  representation of the weak subspace or a representation-invariant subspace
  sampling rule.
- Do not connect any S0 output directly to answer production.  Baseline search
  quota and canonical 512/768-bit replay remain mandatory.

## S1 binding

The charted arm replaces only tail proposal slots in the frozen literal prefix.
It uses logit for two-sided strict bounds, softplus for lower-only bounds,
reflected softplus for upper-only bounds, and identity for unbounded
coordinates.
Its diagnostic is charged to the existing source callback ledger and is capped
at 5% of the aggregate callback cap and 64 callbacks, whichever is smaller.  It
does not probe partially when a complete `h/h2` pair and both symmetric radii
cannot fit.  The first 75% of prefix slots and every fourth counter-Cauchy slot
are retained byte-for-byte.  NaN/empty bounds, invalid semantics, unstable weak
projectors, insufficient budget, and unavailable replacement slots all delegate
the original prefix unchanged.

Both arms use the common four-field `arm.json` contract.  The full worker keeps
the frozen search candidate, final solve-result schema, source replay authority,
reservoir/HP service, PSLQ/exactification path, and canonical descriptor key.
The charted search worker and adapter are independently hash-bound; raw smoke
artifacts live outside Git.

One development source-only transport smoke completed the dry-plan/identical
plan-SHA execute protocol.  The search artifact was accepted, the final schema
remained `geotarget.exp008-finalist-numeric-worker-v15/v1`, source bytes were
unchanged, and the total wall limit was respected.  The selected smoke source
was ineligible for this overlay and exercised fail-closed baseline delegation;
generated S0/unit tests separately exercise activation.  This is interface and
fallback evidence only, not recall or speed evidence.

The current logit/softplus mechanism passed a deterministic generated audit:
variable and residual permutation produced zero normalized proposal drift,
affine bound scaling drift was `3.33e-16`, and every transformed rank-deficient
case activated.  Mixed one-/two-sided proposals remained strictly interior;
the nonsmooth case returned the original prefix.  Callback accounting was
17 expected/17 observed, the first 12 of 16 slots and every fourth insurance
slot were bitwise preserved, and the frozen adapter received the overlaid tail.
AST inspection of the two entries, full/search wrappers and proposal adapter
found zero source identifier literals, sensitive mapping reads, or sensitive
routing conditions.  No truth, expected descriptor, scorer, or formal screen
was used.

## Development145 static applicability

A separate source-bytes-only census discarded every problem ID before feature
extraction and retained no per-case row.  It read no Gold, expected result,
solver result, scorer, or truth data and invoked neither solver nor evaluator.
All 145 formulations parsed with zero bound, residual-expression, or semantic
guard parse failures.

The corpus contains 12 two-sided strict-bound coordinates across seven cases,
zero one-sided strict-bound coordinates, 68 finite coordinates with at least
one inclusive endpoint, and 412 unbounded coordinates.  The one-sided count of
zero is a corpus applicability result; softplus behavior remains covered by the
generated metamorphic audit.

Using only dimension, equation count, parsed bounds, and the frozen S1 budget,
133/145 cases are structurally eligible to attempt the rank diagnostic.  The
nonexclusive static exclusions are seven dimensions below two and six
nonsquare residual-variable systems.  Of the eligible set, 127 contain a
conservatively flagged potentially nonsmooth residual-DAG operation and three
have semantic branch guards; these retain the existing `h/h2`/semantic-pair
fail-close to the original prefix.

Actual weak-rank activation is intentionally recorded as unknown: source bytes
cannot establish the runtime projector stability or the literal anchor's
semantic validity.  Under 256 starts, 600 callbacks/start, and cap 153,600, the
maximum complete diagnostic is 33 callbacks (`0.0215%` of cap), below the
effective 64-callback (`0.0417%`) overlay ceiling and therefore below the
configured 5% limit.  All 133 structurally eligible cases preserve the 192-start
/ 115,200-callback baseline reservation.

An additional truth-free regression smoke used the development source SHA
`63fb3e07117c...`, for which an optimized adapter had exited nonzero when the
search artifact was absent.  Here the frozen champion search child timed out
and produced no `search.json`, but the full worker fail-closed to an empty
reservoir and emitted a completed, schema-valid `RESULT.json` with exit zero,
unchanged source bytes, and wall-budget compliance.  Thus this arm does not
inherit that optimized-adapter safety failure.

Adapted CPQR may be reopened only after the proposal layer receives a
hash-bound arbitrary-precision source residual API at 128/256/512 bits with
ledger-visible callback accounting and without acquiring HP/canonical answer
authority.
