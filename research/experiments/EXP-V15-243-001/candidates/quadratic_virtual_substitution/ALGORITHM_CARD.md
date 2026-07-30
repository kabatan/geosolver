# QUADRATIC_VIRTUAL_SUBSTITUTION — conservative eligibility

## Decision

**Eligibility gate: FAIL. No D0 emitter or connector was implemented.**

Mechanism hash: `536242fd63e7a08f742add19b75f381286f0f268024e516480a270fe2e75ed5a`.

This is the next structurally distinct route after the complete
`SOURCE_LABELLED` family failed its unchanged real-attempt gate. It uses the
digest-pinned exact algebraic exporter to identify source formulations whose
equations and predicates are polynomials of degree at most two over QQ.

The scan found 30 exact-semialgebraic formulations. Six are theoretically
all-QQ quadratic, but only two survive the deliberately conservative D0 caps of
four polynomial variables, 16 atoms, and 16 reconstruction entries. They have
two anonymous structural signatures. The fixed real-emitter gate is four
attempts and two signatures, so the route stops at eligibility.

The six-case number is an upper bound, not a virtual-substitution success
claim. Exact sample-term semantics, sign handling, solution reconstruction,
guard/branch replay, raw-target replay, and the additive baseline connector
have not been implemented or tested. Raising the variable cap from four to ten
would manufacture gate volume without resolving those missing mechanisms and
was therefore not done.

## Custody and authority

- The development partition contains 145 rows; 102 non-development rows are
  skipped by byte-level ID filtering before JSON deserialization.
- No individual ID, value, target, truth, readiness outcome, or formulation is
  emitted.
- The exporter digest is
  `f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318`.
- Eligibility output is aggregate-only and confers no solver authority.
- No formal execute, scorer, full98, truth lookup, or validation/sealed
  formulation was used. CPU was pinned to CPU15 for the original census and
  CPU14 for the deterministic post-lock recheck.
