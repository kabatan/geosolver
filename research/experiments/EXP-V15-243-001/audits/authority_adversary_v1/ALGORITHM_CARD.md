# Authority adversary v1

## Scope

This is a fixed generated falsification suite, not a solver candidate or a
general fuzzer.  It independently attacks three candidate snapshots:

- target-constrained exact NRA witness, commit `0bbc3f8d`, candidate SHA-256
  `7b98bdfb...586ff`;
- certified Hermite D0, commit `db590f31`, candidate SHA-256
  `c0506a29...dbe8` and independent verifier SHA-256 `5189a3ca...c6d`;
- exact point-reflection replay, commit `a0f2edec`, worker SHA-256
  `4dcd978b...974ca` and private candidate SHA-256 `8c9f5b65...6fc4`.

It reads no formal/dev scorer, truth, expected answer, or real case.  Every
execution is generated and pinned to CPU15.

## Acceptance boundary

An output is final authority only when the candidate's own exact untouched
source/equation, guard/selector/branch, definedness, raw-target, proposal
polynomial, isolator, and root-ordinal replay attestations are present and
true.  Backend SAT, a near numerical endpoint, a polynomial-only certificate,
or a partial artifact is never sufficient.

The Hermite D0 certificate deliberately begins after semantic lifting.  Its
independent verifier proves the supplied QQ polynomial problem, but the
certificate has no untouched-source digest or replay.  Therefore verified
Hermite certificates remain provisional and are denied final authority.  This
is a HOLD boundary, not a defect in the stated D0 contract.  Its synchronous
prototype also has no deadline/partial-artifact contract.  A Boolean `Or`
outside its documented polynomial-guard subset raises an uncaught
`AttributeError`; the outer adversary catches it, so it cannot grant authority,
but a source adapter must normalize or reject it explicitly.

## Fixed attacks

The suite covers nonradical/embedded structure, relevant and irrelevant free
coordinates, positive-dimensional target fibres, complex-only systems, wrong
nearby target polynomials, isolator/ordinal corruption, strict boundaries,
Boolean disjunction/selector semantics, phase/full-turn expressions,
`sqrt`/`abs` branches, zero denominators, point/line reflection confusion,
coincident points and degenerate lines, source/hash mismatch, timeout, and
truncated artifacts.  A negative attack returning final authority is reported
immediately as a false authority.
