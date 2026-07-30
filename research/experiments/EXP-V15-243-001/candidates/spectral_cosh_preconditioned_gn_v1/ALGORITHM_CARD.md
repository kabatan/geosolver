# Spectral cosh nonlinear-preconditioned GN — D0 card

- **Hypothesis:** high-growth smooth residuals make an ordinary GN proposal
  take many small Newton contractions.  A fast-growing cosh reference can make
  the step larger before the original merit line search, recovering endpoints
  within the same iteration tranche.
- **Mechanism/state:** from the existing row-equilibrated residual/Jacobian use
  `H=J'J`, `g=J'r`, and H's nondegenerate eigenframe.  With
  `z_i=(V'g)_i/(lambda_i*trust_radius)`, solve `H d = -V q`, where
  `q_i=lambda_i*trust_radius*sqrt(1+z_i^2)*asinh(z_i)`.  This is a directional,
  nonlinear map, not a scalar damping schedule.
- **Allowed inputs:** residual, Jacobian, trust radius, rank/spectrum, smooth-op
  capability, remaining local iteration budget.  No ID, family, target, truth,
  descriptor, or case-result routing.
- **Safety/fallback:** activate only for finite, full-rank, nonrepeated spectra
  and a material direction change.  Otherwise use ordinary GN.  Every endpoint
  is replayed through the original residual and guards.  Only 1/4 of starts use
  this side route; 3/4 remain the untouched baseline.
- **Target failure:** repeated GN contraction/backtracking on polynomial,
  exponential, or other faster-than-quadratic growth, especially when normal
  coordinates are unbalanced.
- **Nearest prior:** adaptive cubic GN changes scalar regularization; spectral
  LM changes linear conditioning; Bregman/Kaczmarz changes residual rows.  None
  applies a nonlinear separable map to normal-gradient coordinates.  Archive
  `rg` found no cosh/asinh normal-gradient preconditioner.
- **Causal entry/reopen gate:** only retain beyond D0 if the ordinary lane shows
  large model Newton coordinates and the nonlinear direction is non-collinear,
  while gains survive rotations/residual permutations and canonical replay.
- **Prototype budget:** under 30 minutes; candidate-local Python only.  No
  runner/compiler/framework changes.
- **Primary source:** Bodard and Patrinos, *Newton methods beyond Hessian
  Lipschitz continuity: A nonlinear preconditioning approach* (2026),
  https://arxiv.org/abs/2605.12666 .  Equations (PN) and the separable-reference
  formula motivate the RHS; the spectral frame and trust-radius scale are this
  campaign's orthogonal-invariance adaptation.

## Current campaign connection

Status: `CURRENT_CAMPAIGN_SOURCE_SEAM_PASS; FORMAL_OWNER_SCREEN_REQUIRED`.

- Arm: `spectral-cosh-current-campaign-v1`.
- Entrypoint: `integrated_worker.py`.
- Entrypoint SHA-256:
  `885151dafe4b7592848c47cba71215bbe5460f85e3f9820ad734ab37057d57d0`.
- Current progressive-adaptive wrapper SHA-256:
  `4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4`.

The entrypoint loads the hash-pinned current `64 -> 600` adaptive full worker
and changes only its search executable. In the search child it retains the
current scheduler, proposal prefix, callback ledger, process deadline, source
evaluator, guards and replay. Immediately before each isolated rung, the
already available original start ordinal selects the local module: ordinals
congruent to 3 modulo 4 use the spectral-cosh RHS wrapper; all others keep the
frozen local module. Probe and handoff reexecutions of the same original start
therefore use the same route. HP, restoration, exact descriptors and final
authority remain the current worker's original objects.

The candidate module exposes the parent's original configuration. If every
attempted spectral transform fails closed, it passes the exact original RHS at
every linearization and removes only the three candidate telemetry keys. The
resulting endpoint/status/counter serialization is byte-identical to the
baseline seam result. Rank deficiency, repeated eigenframes, nonsmooth/branch
source tokens, nonfinite models and negligible transforms all take this
fallback.

The short CPU-31 source seam suite passed `14/14`. It verifies the 3/4 baseline
quota, stable original-ordinal routing, dependency hashes, unchanged guarded
case/source program/literal prefix/deadline object custody, current HP/final
authority custody, smooth/branch source gating, rank/eigenframe fallback and
byte-identical zero-activation serialization. The original generated D0
reproduced unchanged: 37 generated systems, `17` wins, `0` losses, `0` false,
`0` extra, and 75/25 routing. No benchmark truth, scorer, case outcome,
validation, sealed or holdout data was read. No formal score or speed claim is
made here.
