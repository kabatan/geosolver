# CENSOR_AWARE_PROOF_RUNG_INDEX D0

## Hypothesis

An exact-authority side lane can allocate resumable proof rungs better than
FIFO, round-robin, or static public shortest-first by estimating discrete
completion hazard from observed rung completions and right-censored slices.
The policy may see only public rung estimates, proof progress, elapsed observed
time, service/wait state, and accumulated completion/censor counts.

The ordinary baseline is byte-independent of this policy, reserves and spends
exactly 75% of total budget, and the experimental lane is capped at 25%.

## Disposable mechanism

The prototype keeps posterior hazards by `(progress rung, elapsed bucket)` and
by progress rung overall.  Its index combines those hazards with bounded
certificate nearness and waiting age.  A hard first-service stratum prevents
starvation.  Terminal tasks are removed permanently.  Hidden durations and
success bits live in the simulator and are never passed to the policy.

No geometry, corpus, formal result, runtime manifest, scorer, or truth artifact
is read.  Four fixed synthetic families use 64 scenarios each.  FIFO,
round-robin, static-shortest, and the candidate yield 1,024 strategy traces;
256 hidden-future twins raise the total to 1,280.

## D0 and repair

Initial D0 was safe but improved zero families against the strongest comparator.
Its supposed late/censored decoys could still finish within the 25-unit side
budget, and the progress multiplier overwhelmed falling hazard.

Repair A changed the mathematical mechanism to mix elapsed-bucket and aggregate
rung hazard with a bounded progress factor.  It also made the censored branch
actually exceed the side budget.  This produced a strict late-success gain,
but only one of four families improved.  Nonstationary traces still regressed.

## Decision

**STOP.**  The fixed gate requires improvement in at least two independent
families and no baseline loss.  Baseline loss, future leak, starvation safety,
and terminal resurrection were all zero, but only one family improved and one
family had certificate regression.  Further radius, prior-weight, or progress
coefficient tuning is prohibited.

Reopen only for a genuinely different mechanism that estimates finite-horizon
certificate probability under nonstationary/competing rung hazards, with the
same hidden-future and hard 75/25 tests.  This candidate is not for integration.
