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

