# Quadratic virtual substitution source-closure / novelty audit

Verdict: **PASS only to a disposable current-source connector D0; HOLD corpus
execution until canonical full-source replay is joined.**

Audited prototype head: `9464ec55f03c74d168be86a93fadd98410e27508`.
Repair-A core SHA-256:
`d9cea2aeb0273bd6fcb5c730a2fc01a50ac7160f766e9d17301761fbc3e05643`.
Aggregate SHA authority is in `AGGREGATE.json`.

Only the 145 canonical source JSON files under the benchmark-owner supplied
input root were read. Raw bytes were SHA-bound, then top-level `id` was removed
before the pinned compiler. No RESULT, PLAN, artifact, score, truth, individual
path/hash/target, or per-source disposition was read or emitted. No formal,
lock, solver, msolve, Julia, or heavy execution occurred.

## Truth-blind static upper ceiling

- The pinned current compiler accepted 27/145 projections.
- Twenty-six had every compiled equation and predicate at individual-variable
  degree at most two over QQ.
- Twenty-one also had a distinct equation-variable matching whose optimistic
  linear/quadratic branch product is at most 64. They span 21 anonymous
  structural signatures, comfortably above the required 4-source / 2-signature
  gate.
- The 21-source ceiling covers dimensions 2 through 24 and branch products 1
  through 64. Fourteen have no explicit branch replay obligation; seven have
  one to three obligations.
- This is an upper ceiling, not an activation claim. Matching product ignores
  substitution-induced degree growth, leading-coefficient case splits,
  duplicate sheets, coefficient swell, and exact replay rejection.

## Source semantics closure

The synthetic prototype by itself is not source-authoritative. Its local
`_exact_replay` checks only already-lowered SymPy equations, guards, and
denominators; its target descriptor uses numerical nearest-root selection. It
does not parse the geometry DSL, replay construction definedness/branch
semantics, or prove raw-target linkage.

A current-source D0 is therefore permitted only with all of these conjuncts:

1. Bind raw source bytes/SHA and the deterministic id-free projection SHA.
2. Use the pinned compiler equations and predicates only for proposal
   enumeration. Preserve every denominator/strict predicate and leading-zero /
   discriminant branch condition.
3. Return every candidate configuration to the untouched canonical exact
   source replay. That replay, not the QVS prototype, must prove construction,
   source relations, guards, bounds, definedness, every branch selector, and
   exact raw-target equality.
4. Build the minimal polynomial, isolator, multiplicity, and factor-local real
   root ordinal from exact replay. Numeric nearest-root selection is forbidden.
5. The seven branch-bearing sources require an executed obligation ledger. The
   msolve connector's current count-only `canonical_branch_replay` boolean is
   not reusable because its independent audit found that replay obligations
   were not joined to exact worker evidence.
6. Fail closed on branch state 65, degree growth above two, unsupported exact
   operations, or incomplete replay, while leaving at least 75% baseline quota.

## Novelty

This mechanism is not an RUR or triangular-decomposition duplicate. RUR builds
a global univariate parametrization and selects an exact factor/box; triangular
routes construct algebraic towers/regular chains. QVS instead chooses a
min-fill equation-variable pair and explicitly enumerates degree-1/2 root
terms with leading-coefficient, discriminant, denominator, and sign conditions.
Its state, failure modes, and useful source stratum are therefore orthogonal
enough for one connector D0.

The earlier conservative QVS eligibility artifact found only two sources under
a four-variable cap. Repair A plus the current compiler yields a new 21-source
optimistic ceiling without relaxing the fixed 64-state branch cap, satisfying
the reopen/recurrence gate. This does not authorize parameter tuning or a heavy
run. If a disposable connector cannot preserve the six closure conjuncts, the
route must STOP rather than fall back to a generic RUR/triangular backend.
