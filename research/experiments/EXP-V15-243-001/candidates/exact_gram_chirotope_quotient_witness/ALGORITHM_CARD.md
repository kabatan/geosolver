# EXACT_GRAM_CHIROTOPE_QUOTIENT_WITNESS — source-only eligibility + D0

## Decision

**Source-only eligibility gate: PASS. Generated D0: PASS. Real connector/formal: HOLD.**

Mechanism hash: `8cafcec7328351d032fa268c392d032c1a75c51bbff2f0cf6904bb78843c541d`.

The route does not exactify every Cartesian coordinate. It treats the complete
squared-distance matrix, its anchored Gram quotient, exact orientation signs,
and selector bits as authority. One QQBar realization is reconstructed only
after those invariants pass, solely to replay the untouched source guards,
branch, and raw invariant target.

## Truth-free development eligibility

The occurrence-complete scanner uses a closed, site-sensitive operator
whitelist. It rejects every call outside that whitelist, every component or
attribute read, chart/bound use, raw scalar variable outside a `Point` proposal
chart, raw scalar target, dynamic call, and non-invariant AST escape.

- development sources: 145;
- eligible attempts: 15;
- anonymous structural signatures: 15;
- required gate: at least 4 attempts and 2 signatures;
- gate result: PASS.

The 102 nondevelopment rows were discarded by raw partition identity before
JSON deserialization. No individual ID, target, truth, eligibility result, or
outcome was emitted. The count is an operator-surface upper bound, not an
activation, authority, solvability, score, or recall claim.

## Exact certificate

For a candidate-private exact invariant source ledger, D0 proves:

- EDM symmetry, nonnegative off-diagonal entries, and exact hollow diagonal;
- the anchored identity `G_ij = (d_0i + d_0j - d_ij)/2`;
- exact PSD through all principal minors;
- exact Gram rank at most two, hence every 3x3 Gram minor vanishes;
- a non-collinear exact orientation choice with a non-near-zero numerical
  proposal sign;
- a single radical/QQBar realization anchored at the chosen oriented triple;
- exact replay of every squared distance, chirotope guard, selector bit, and
  raw invariant target against the untouched source digest.

Missing orientation choice is a hard mirror ambiguity, even when the EDM is
otherwise valid. Rank three, near-zero orientation proposals, absolute
coordinate guards, bounds, raw scalar use, non-invariant operations, malformed
EDM, or selector disagreement fail closed.

## Generated S0

- 3/3 positive families authorize and independently verify: rational triangle,
  four-point rectangle, and radical QQBar realization;
- point permutation, 90-degree rotation, and reflection for every family:
  9/9 authorize and independently verify;
- same EDM under reflection retains distances while exact chirotope sign and
  selector bit both flip;
- rank3 Gram, same-EDM mirror ambiguity, near-zero orientation, and absolute
  coordinate guard: 0/4 false authorities;
- certificate mutations to target, rank, EDM, or QQBar realization are rejected;
- 8/8 unit tests pass on CPU15.

## Portfolio boundary

`or_connector.py` is additive only. The baseline is called first, retains 80%
of the declared confirmation budget (above the required 75%), and wins if it
has authority. Any side-route failure or exception returns the exact baseline
object by identity.

There is intentionally no common compiler and no real OMC connector in D0. The
reopen gate is a candidate-private emitter that maps an eligible source and an
ordinary proposal into a complete exact invariant ledger, followed by this
independent canonical replay. Until that exists, the 15-source count must not
be interpreted as executable applicability.

No formal execute, scorer, full98, truth lookup, validation/sealed formulation,
or CPU other than CPU15 was used.
