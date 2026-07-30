# Adaptive scheduler core handoff

This is the current S2 winner, not a holdout-qualified release.  It is kept on
`experiment`; nothing is merged into `main`.

## Frozen identity

- Arm: `progressive-adaptive-hybrid-v1`
- Mechanism/entrypoint SHA-256:
  `7d6f168d8679732c672842e6b7a44573d190449ad0fbe4cc09a7b9112ddc9500`
- Exact common-control entrypoint SHA-256:
  `e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301`
- Product reference: detached clean commit
  `0967ff1cde5c2435fe0207da65e8779ff24a6da6`

The experimental implementation lives in
`research/experiments/EXP-V15-243-001/candidates/progressive_adaptive_hybrid_v1`.
The reusable scheduling types and accounting helpers it hash-binds live in
`progressive_local_budget_v1/candidate.py`.

For a later production port, the algorithm core is only the scheduler policy:

1. service immutable original-prefix starts in blocks of eight with a
   64-callback probe;
2. cap a probe by
   `max(0.5, min(4, 2 * remaining_seconds / unserved_starts))`;
3. after a completed block, hand at most half its starts directly to a fresh
   canonical 600-callback service;
4. reserve 25% of handoff capacity for original-order baseline starts and 25%
   for counter-Cauchy insurance, and rank the rest only by semantic validity,
   residual/guard merit, model ratio, rank stability, charged work, and
   ambiguity;
5. retain the four-second cap only for a probe that timed out or consumed at
   least 90% of its admission cap; otherwise give a deep handoff the remaining
   global wall horizon;
6. change neither HP/restoration nor canonical source replay, descriptor
   authority, exact-set deduplication, or extra rejection.

No checkpoint/resume capability is assumed; a deep handoff is deliberately
charged as reexecution.  No problem ID, family, figure name, target count,
answer, or prior score is a routing feature.

## Experiment commits

- `3f822909`: disposable progressive accounting/types and S0 tests.
- `d9e4350c`: adaptive hybrid mechanism and generated/metamorphic tests.
- `81ea59d4`: corrected binding through the exact common-control champion
  stack.  Earlier binding evidence is superseded and must not be reused.

A production porter should copy the policy into the maintained search seam,
not copy the experimental wrapper/import machinery.  The required acceptance
tests are the no-op common-control differential, proposal-prefix preservation,
all-start first service, baseline/Cauchy quota accounting, starvation timeout,
metamorphic permutation/scaling invariance, canonical replay, and the formal
S3/holdout gates.  Any policy change gets a new mechanism hash and returns to
S0; S2 case identities are not a tuning source.

Validation and sealed inputs remain unopened.
