# EXP-MULTITARGET-001 adaptive slack v2

## Hypothesis

V1's S1 losses are causally compatible with its pre-answer six-second tail
reserve and three-second replay window. A loss-safe continuation route must be
a monotone extension: reproduce all frozen work first, then use only wall time
that the frozen service returned unused after it already confirmed at least one
canonical descriptor.

## Mechanism and frozen boundary

- Frozen numerical-v15 worker SHA-256:
  `330e52c75b98d3c58a1422cec415b5a53673ebafb7e90789a271df34a308309d`.
- Entrypoint SHA-256:
  `004f2c526de350dab5f7e1c06f8fbfe0101fd58c54a26ae9fc70586ff74d5aa1`.
- Scheduling mechanism SHA-256:
  `3457f9ed08d10c87746d0610a351c6a04434c559364556cb6e319750d88fda65`.
- No patch to search seconds, starts, callbacks, aggregate cap, seed, Python,
  selection reserve, fresh replay, finalization reserve, or hard deadline.
- No pre-answer reserve and no reorder of any frozen primary, alternate, or
  restoration wave, including after authority.
- After every frozen wave completes, an existing frozen authority pass enables
  a truth-free ranking of unattempted replay candidates by affine-invariant
  provisional-target novelty, configuration novelty, and residual rank.
- Slack HP calls use a six-second maximum and the frozen three-second minimum.
  A fast failed slack call may use remaining time in the frozen restoration
  seam. Canonical source replay and exact descriptor authority are unchanged.

The seam cannot observe descriptor confirmation during numerical search. The
first observation is the result of frozen HP authority after discovery and
fresh replay; therefore v2 is deliberately post-exact-answer-only.

## Truth-free trace and metamorphic S0

`test_post_answer_v2.py` executes the actual hash-bound frozen
`_service_candidates` as the reference and replaces only HP/restoration child
processes with deterministic truth-free outcomes. It records attempt kind,
endpoint digest, output path, source path/SHA, CPU, and `float.hex()` timeout.

- No-authority trace: candidate and control are fully equal, including every
  primary, alternate, and restoration event and attempt document.
- Authority trace: the complete frozen trace is an exact prefix; slack calls
  are appended only afterward.
- Delayed authority: the failed-first/successful-second prefix is exact.
- The diversity function is made to raise if touched in a no-authority run,
  proving the pre-answer lane is unreachable.
- Candidate permutation and positive/negative invertible affine target
  transforms preserve the post-answer ranking.
- Frozen and decorated dry-plan fields compare equal except schema/provenance;
  selection reserve remains one second.

All EXP-MULTITARGET mechanism tests pass: 18/18 (six v2 trace/metamorphic tests
and twelve retained v1 tests). No scorer, truth, formal corpus, validation, sealed,
or per-case benchmark result was used.

## Generated execution smoke

A generated one-variable circle formulation was run outside the repository via
the normal two-phase dry/execute CLI at 10 seconds total, 4 seconds search,
eight starts, 64 callbacks/start, seed 0, one pinned CPU, and one native thread.
The frozen search artifact was accepted, canonical authority returned one exact
descriptor, source bytes were unchanged, the v15 result schema was preserved,
and elapsed wall time was 2.8562 seconds. The adaptive gate activated after the
first authority; there was no deferred endpoint, so it added no work. Raw
artifacts remain outside Git.

## Promotion/reopen gate

Benchmark owner may run S1 without sharing case identities. Promote only if
safety stays clean and the v1 recurring losses disappear. If v2 still loses a
control case, this post-answer seam is not a sufficient causal fix and the lane
stops; do not add another pre-answer reserve or replay modification. Reopen only
with aggregate trace evidence that the common harness differs before authority
despite the frozen-prefix contract, or with a new worker seam that can confirm
a descriptor during discovery without changing control discovery.
