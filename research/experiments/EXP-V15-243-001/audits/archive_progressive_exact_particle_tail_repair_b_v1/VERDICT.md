# Frozen audit: particle Repair-B exact surplus tail

- Frozen implementation: `742e7f4dec0efbc46a90b38d6c6ff444cb9ffb4a`
- Arm entrypoint SHA-256: `393dfad15e96ea42014aa2ff3f3b2f461ad46302ddea2c9049d818253ec10bee`
- Scheduler SHA-256: `20e186041a448a3bb1331096c01b328939512767f498422335294b85d5ceccf1`
- Audit execution: CPU 14, candidate-local tests `6/6 PASS`; no corpus, scorer,
  truth, `--execute`, screen24, or heavy HP run was used.

## Disposition

**STOP before formal screen24.** The reopen is mathematically distinct and
causal, but the executable mechanism is not yet transitively hash-closed.

The prior full particle replacement lost ordinary coverage. Repair A made the
side lane surplus-only but had no useful activation when the frozen AD
interpreter rejected otherwise-smooth rows. Repair B retains the completed
progressive exact-outer result, sends at most one quarter of the original
callback/wall allowance to an independent tail, admits only full-AD or a
source-gated smooth all-FD Jacobian, charges the one-sided FD calls, fresh
replays endpoints, and appends only descriptors accepted by the existing exact
authority. Mixed, branch/nonsmooth, malformed, no-budget, no-novelty, and
pre-commit failure paths retain the baseline bytes. This is not a threshold or
radius retune and satisfies the recorded reopen gate.

## Causal blockers and smallest repair

1. `worker.py` sets the scheduler path but does not pin
   `scheduler_shim.py`. The arm and entrypoint hashes therefore remain valid
   if the complete scheduler/tail mechanism is replaced.
2. The pinned particle `real_search_worker.py` loads the frozen
   `EXP-REAL61-008/dev41_restoration_filter_v3/worker.py` without checking its
   bytes. The current observed digest is
   `17bfea52e7da6c3cca58c5baabcb120017714cbbf2ecfa53428cb1c81d6636dc`.

Repair only these bindings: pin the scheduler digest in `worker.py` at import
and runtime assertion; pin the shared source-worker digest in
`real_search_worker.py`; then cascade the changed real-worker, tail-wrapper,
scheduler, entrypoint, and `arm.json` hashes. Add negative mutation tests for
both files. Do not alter numerical policy, quotas, exact authority, or
deadline. A fresh independent audit must recompute the closure before formal
execution.

## Safety boundary and prospective screen

Static inspection found no ID/family/truth/answer/known-count routing. Source
SHA is rechecked before the atomic descriptor union; the immutable baseline
prefix is compared exactly; endpoint candidates go through fresh replay and
the already-installed exact outer authority. Candidate-local direct invocation
does not own the machine-wide benchmark lock and is ineligible for evidence.
The existing `EXP-GLOBAL-001/run_arm.py` must be the sole launcher: jobs=1,
one pinned physical CPU, fresh process per case, one native thread, outer
process-group/RSS/deadline guard, and its nonblocking global benchmark lock.

After the two closure repairs, freeze the exact-outer progressive base as A and
this tail as B. Run screen24 at 30 s total / 20 s search, 256 starts, 600
callbacks/start, aggregate cap 153600, seeds 0,1,2, with one `A,B,B,A` sequence
per seed and new output roots for every leg. Freeze source-panel, runner,
scorer, runtime/version, arm, entrypoint, and transitive mechanism hashes
before the first leg. Workers receive formulation bytes and SHA only; scoring
occurs after worker exit. Any closure drift, contention, incomplete leg,
timeout, malformed result, descendant leak, extra/invalid descriptor, or
baseline-prefix change is a failed leg, not a retry. This audit does not
authorize the screen until the closure repair is independently verified.
