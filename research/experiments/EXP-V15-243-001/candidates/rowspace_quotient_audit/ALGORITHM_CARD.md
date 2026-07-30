# Rowspace quotient with null-component insurance: pre-code audit

Status: `STOP_BEFORE_CODE_DUPLICATE_CLOSED_COMPOSITION`.

The proposed lane would activate at an ill-conditioned full-space LM state,
split the scaled Jacobian into row-space and null-space coordinates, converge
the solvable quotient first, and retain Cauchy/IID exploration in the null
component.  It would preserve at least 75% ordinary search and would never
emit without fresh source replay.

The archive already contains both transition mechanisms:

- `epoch_b_rowspace_quotient_stratum_portal_g0` stores the minimum-norm
  affine anchor, null projector, and rank, then re-enters the ordinary solver.
  It passed generated G0 with complete-set `+240/-0`, false `0`, work ratio
  `1.0`, and metamorphic `192/192`.
- the closed spectral branch/nullspace lineage already combines a weak/right
  singular subspace with full-support Cauchy mixing, antithetic trust-radius
  launches, ordinary completion, and fresh replay.  Its insurance-heavy
  second wave removed the prior narrow gain and retained a fold regression.

Conditioning the same operators on an LM condition-number trigger changes
only activation.  It supplies no new mathematical state and does not satisfy
the recorded reopen requirement.  No candidate code, generated corpus, real
case, truth, target, scorer, or authority path was created for this proposal.

The lane was therefore switched, as preregistered, to a primary-research
persistent-dual greedy randomized Bregman--Kaczmarz experiment.
