# EXP-JAC-003 — terminal formal-protocol failure

`EXP-JAC-003` is closed without an algorithmic result.  Its frozen development
launch stopped before K0 preflight and before the first ABBA segment, so it
cannot support a claim about the cached routed Jacobian candidate's correctness,
formal safety, efficacy or speed.  It also does not justify rejecting that
candidate algorithm.

## Intended question

The frozen study was designed to compare the public dense finite-difference K0
control with a compiler-derived cached/routed K1 candidate, using fresh-process
K0/K1/K1/K0 segments after independent safety and exact K0 replay preflights.
Candidate-visible inputs excluded Gold, family identity and opaque join keys.
The preregistration, visibility contract and source lock remain useful protocol
records, but the planned comparison was never reached.

## Terminal chronology

1. The pre-binding audit passed before outcome access and bound the frozen
   source, inputs, runner and publication chain.
2. The formal child completed environment setup, frozen source tests, public
   surface replay and candidate safety capture.
3. The frozen safety assessor rejected a JSON numeric-representation contract
   mismatch before K0 preflight.
4. No K0 or K1 segment ran.  The preserved partial archive has zero segment
   traces and no terminal capture receipt.
5. The independent host receipt recorded contention and a monitor failure.
   Consequently, there is no authoritative performance observation even apart
   from the pre-segment termination.
6. A post-outcome safety-only replay was retained to diagnose the protocol
   boundary.  It is explicitly non-authoritative and is not a replacement for
   the missing K0, ABBA, correctness, safety or timing evidence.

The raw launch receipts and partial bytes were preserved rather than repaired
or republished.  Their hashes and the forensic claim boundary are recorded in
[`development-failed-v0`](../../research/results/EXP-JAC-003/development-failed-v0/CLAIM_BOUNDARY.md).

## Claim boundary

The evidence supports only these statements:

- the frozen attempt terminated in the safety-assessment protocol before K0;
- no ABBA segment outcome exists;
- the observed host was not clean enough to authorize a timing claim; and
- the attempt is terminal under `EXP-JAC-003`.

It does **not** establish any of the following:

- that K1 is correct or incorrect relative to K0;
- that K1 is formally safe or unsafe;
- that K1 preserves or improves solution recovery;
- that caching/routing is faster or slower; or
- that the mechanism should enter or be removed from production.

The frozen decision is therefore: no retry under this ID, no locked validation,
`locked=false`, and `product_connected=false`.

## Successor gate

A successor must use a new experiment ID and fresh preregistration.  Before any
outcome-bearing launch it must freeze and test a serialization contract that
round-trips every assessor-consumed numeric type, and it must prove that the
safety assessor and exact K0 replay can complete on result-blind fixtures.  The
formal attempt must then obtain a clean uncontended host receipt, pass every
preflight and complete the full ABBA development sequence.  Only a passing new
development gate may authorize family-disjoint locked validation; only locked
validation may authorize product connection.

See [EVID-21](EVIDENCE.md) and the machine-readable
[`NEG-015`](../../research/negative-results/ledger.json) closure.
