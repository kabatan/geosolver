# EXP-GLOBAL-001 campaign card

## Hypothesis

The remaining development failures are dominated by root discovery, long
single-start starvation, post-answer tail starvation, and rank/guard geometry.
The campaign tests those mechanisms independently before combining them.  A
structural side route is allowed only when applicability can be decided from
the untouched formulation.

## Fixed boundaries

- Python champion only; the clean-slate Julia solver is not a replacement arm.
- No case ID, family name, answer, truth, or previous score enters routing.
- Validation and sealed inputs are unavailable until one final candidate is
  frozen.  Their per-case outcomes will never be published to candidate arms.
- The source formulation, final original-source replay, exact descriptor
  authority, and duplicate/extra rejection remain unchanged.
- The dirty/current `main` worktree is not an implementation source.  The only
  product reference is detached commit `0967ff1cde5c2435fe0207da65e8779ff24a6da6`.

## Stages

1. S0 generated/mechanism tests and fail-closed contract checks.
2. S1 screen24 at 30/20 seconds, seeds 0–2, jobs=1.
3. S2 screen60 plus group-disjoint development folds and metamorphic tests.
4. S3 development145 at 180/146 seconds, seeds 0–4, ABBA jobs=1 followed by
   jobs=7 throughput.
5. One aggregate-only validation+sealed audit for the frozen finalist, then a
   full243 confirmation.  No post-holdout tuning is allowed.

Recall promotion requires safety counts to remain zero, positive net exact-set
delta in at least four of five seeds, gains across at least two groups, and a
nonnegative family-clustered 95% lower bound.  A speed-only arm requires recall
noninferiority, no recurring loss, at least 15% paired geometric-mean speedup
and 5% p95 speedup, or 20% more completed starts at equal wall time.

## Lane disposition

- Progressive local racing: test both preregistered tranche profiles; retain
  the Cauchy insurance floor and first service for every start.
- Multi-target tail: continue after the first descriptor and preserve
  primary/alternate/restoration service.
- Rank/guard: promote adapted CPQR and charted weak-direction proposals as
  separate arms; unchanged weak-to-adaptive remains blocked by representation
  disagreement.
- Evaluator: require bit equality for pure speed paths; test incremental
  reservoir reconstruction separately from cached sparsity/AD.
- Structure: keep as an applicability-limited side route with at least 50%
  baseline quota; every endpoint is only a proposal to the canonical verifier.

An arm is stopped immediately for an extra/duplicate/invalid descriptor,
source mutation, zero mechanism activation, or more than 20% work regression
without a recall signal.  A stopped mechanism is not reopened without a
documented causal gate.
