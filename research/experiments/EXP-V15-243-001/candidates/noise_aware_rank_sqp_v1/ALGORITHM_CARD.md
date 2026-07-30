# Noise-aware rank-deficient SQP polish — D0 card

- **Hypothesis:** fixed CPQR cutoffs and exact Armijo tests misclassify a
  rank-deficient plateau when finite-difference error is as large as the weak
  singular directions. Empirically measured function/Jacobian noise can set
  the rank cutoff, merit relaxation, and stopping floor, allowing a bounded
  normal/tangential rescue without spending the 75% baseline quota.
- **Mechanism/state:** two charged same-point residual evaluations estimate
  `epsilon_F`; independent central FD stencils at `h` and `h/2` estimate
  `epsilon_J`. CPQR ranks both stencils under the measured threshold. Only
  adjacent stable rank deficiency plus a noise-floor merit plateau activates.
  CPQR-independent rows define the normal step; dependent rows define a
  null-space tangential step. The original row-scaled residual accepts trials
  with a relaxation proportional to `epsilon_F + epsilon_J*||step||`.
- **Paper adaptation:** Berahas, Shi, and Zhou, *Optimistic Noise-Aware
  Sequential Quadratic Programming for Equality Constrained Optimization with
  Rank-Deficient Jacobians* (2025),
  https://arxiv.org/abs/2503.06702 . Their bounded-noise optimistic feasibility,
  Byrd--Omojokun normal/tangential decomposition, and relaxed merit line search
  motivate the mechanism. This root-finding D0 treats CPQR-independent residual
  rows as constraints and dependent rows as the tangential merit; it is a
  disposable adaptation, not a claim to reproduce their full optimizer.
- **Allowed state/routing:** repeat-FD values, row scales, CPQR rank agreement,
  normal/tangential vectors, merit history, measured noise floor, smooth-op
  capability, start ordinal, and remaining local budget only. No problem ID,
  family, target, truth, descriptor, or prior case outcome is visible.
- **Safety/fallback:** exactly one in four starts may use the rescue; three in
  four stay baseline. Both D0 arms pay the identical repeat-FD and line-search
  callbacks. Opaque/nonfinite, full-rank, unstable-rank, nonplateau, and
  noise-satisfied states use the baseline proposal. Every endpoint is replayed
  through the original residual and guards; the rescue grants no authority.
- **Nearest prior / non-duplication:** `ad_elastic_trust_funnel_v8` already has
  fixed-rank normal/tangential steps; row restoration has fixed CPQR/filter
  fallbacks; filtered LM estimates analytic roundoff without step decomposition.
  The new causal signature is complete only when
  `repeat epsilon_F/epsilon_J -> CPQR rank -> normal+tangential step ->
  noise-floor merit gate` fires. Radius/cutoff tuning alone does not reopen them.
- **D0 gate:** at least three unrelated positive families, full-rank/opaque/
  inconsistent negatives, strict wins, loss/false/extra zero, exact callback
  parity, 75% baseline, and residual/variable permutation-scale metamorphic
  parity. Failure reopens only with a different noise estimator or inexact
  subproblem mechanism, not threshold/radius/seed tuning.
- **Prototype scope:** candidate-local Python only, under 30 minutes; no shared
  SQP framework, runner/compiler changes, formal truth, or production work.

## D0 result

Fifty-four generated cases across eight families produced `30 wins / 0 losses /
false 0 / extra 0`. All four positive families activated (32 total stable-rank
tangential rescues); full-rank, opaque, and inconsistent negatives activated
zero times. Empirical `epsilon_F` was nonzero on all eight bounded-noise cases;
`epsilon_J` was nonzero on all 50 due to independent stencil discrepancy.
Control and candidate each used exactly 6,774 callbacks, with zero per-case
mismatches. The portfolio map is exactly 75% baseline / 25% side. Seven tests
passed, including residual and variable permutation/scale metamorphics. The
causal ablation held the mean Jacobian fixed while measured-noise rank
crossed, verified a nonzero normal plus null-space tangential decomposition,
and made the same raw merit trial reject below but accept above the measured
noise floor. A shape-changing FD negative also exercised fixed callback padding.
This is
generated mechanism evidence only; no formal truth/scorer or case outcome was
read. Formal D1 is owned by the root benchmark agent.
