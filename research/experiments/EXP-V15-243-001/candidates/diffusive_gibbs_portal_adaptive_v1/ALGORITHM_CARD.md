# Diffusive-Gibbs portal + current adaptive arm (D0 connection)

## Hypothesis

The generated-corpus DiGS survivor may expose remote basins to the current
64→600 adaptive solver without changing source semantics, local solving, HP,
reservoir handling, or final canonical replay.

## Candidate-only mechanism

Before the current adaptive `run_local_arm`, the adapter builds the frozen
truth-blind affine chart from immutable starts and runs the frozen DiGS kernel
in the existing fork-isolation/accounting mechanism.  It may spend at most 64
callbacks and at most 25% of the aggregate callback cap.  At most four
non-insurance coordinates are replaced, after which the current adaptive arm
is invoked exactly once.

Every ordinal divisible by four is preserved byte-for-byte.  At least 75% of
all original start bytes are preserved, source tags are unchanged, proposals
outside explicit source bounds are rejected, and any ineligibility, timeout,
child error, malformed proposal, or zero-proposal result fails closed to the
original prefix.  A timed-out child is terminated/killed if necessary, reaped,
and its already-charged callback is reconciled into the shared budget.

## Frozen closure

- Current adaptive adapter: `4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea`
- Truth-blind chart portal: `7cb8acd0cf867e4adf19d0b5b969c8839cf34215b97b03a9e1a47dd11cba068d`
- Frozen DiGS kernel: `e53660ad093682662ab4056ef11d6fece82d1ea9ffa46e8bbce0389ce4278df6`
- Entry point: `195fa898893c7d6a07d8494ead94e979b67e2c9fe7bbfe93dd54639741403016`

## D0 connection result

Three source-only runs completed without scorer or benchmark truth.  One run
activated with 28 charged scout callbacks and inserted two proposals while
preserving 62/64 start points.  One expensive scout was preempted and reaped,
then fell back; one short-deadline run took the zero-callback fallback.  All
three retained source bytes and completed inside their worker deadline.

Decision: `PASS_D0_CONNECTION_SMOKE_ONLY`.  This is eligible for benchmark
owner measurement; it makes no recall, exact-set, or speed claim.

## Reopen / stop gate

Stop if S1 shows no activation, any source/replay/insurance violation, callback
accounting mismatch, or more than 20% work regression without recall signal.
Only the benchmark owner may inspect correctness or run a formal scorer.
