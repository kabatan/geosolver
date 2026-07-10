# EXP-DEF-001 corrected development decision

Decision: **bounded-negative-stop-before-locked**

Selected variant: `None`

The Julia runner and formal preflight did not open Gold, even for hashing. The analyzer verified the self-excluding v4 source freeze, preserved failed-attempt evidence, clean source HEAD blobs, exclusive-run audit, execution identity and every raw hash before its first Gold access.

This decision was independently recomputed from those identity-bound raw rows by the Python analyzer.

## Claim boundary

This v2 run is an ideal-Jacobian mechanism and safety gate. Its analytic Jacobian callbacks are work-charged like central finite differences, but they do not test the production finite-difference error model or arbitrary plugin AD behavior.

A passing decision advances only to `advance-to-derivative-realistic-development`. It does not authorize locked inputs, a black-box product speedup claim, production connection, or product readiness.

## Safety

- `A0-ORDINARY-LMQR`: false_accepted=1880, positive_residual_promotion=512, dgn_singular_acceptance=0, measured_rank_route_violation=0, canonical_bypass=0, budget_violation=0, ordinary_fairness_violation=0, deadline_violation=0
- `A1-SHIFTED-RESIDUAL-DEF`: false_accepted=634, positive_residual_promotion=260, dgn_singular_acceptance=0, measured_rank_route_violation=0, canonical_bypass=0, budget_violation=0, ordinary_fairness_violation=0, deadline_violation=0
- `A2-DGN-REFERENCE`: false_accepted=294, positive_residual_promotion=260, dgn_singular_acceptance=2, measured_rank_route_violation=0, canonical_bypass=0, budget_violation=0, ordinary_fairness_violation=0, deadline_violation=0
- `D1-DGN-MIXED`: false_accepted=1476, positive_residual_promotion=448, dgn_singular_acceptance=0, measured_rank_route_violation=0, canonical_bypass=0, budget_violation=0, ordinary_fairness_violation=0, deadline_violation=0
- `D2-DGN-FAIR-RETRY`: false_accepted=1880, positive_residual_promotion=512, dgn_singular_acceptance=0, measured_rank_route_violation=0, canonical_bypass=0, budget_violation=0, ordinary_fairness_violation=0, deadline_violation=0

Metamorphic disagreements: 2

No locked input was generated or opened by this analysis.
