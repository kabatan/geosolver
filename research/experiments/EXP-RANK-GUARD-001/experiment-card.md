# EXP-RANK-GUARD-001 experiment card

Status: **S0 complete; non-promotional**.

## Hypotheses

- The frozen `EXP-LOCAL-015` adapted CPQR signal can be recovered by fixing
  aggregation conformance without changing candidate mechanics.
- A callback-bound weak right-singular line can generate symmetric starts with
  exact callback accounting and no representation-dependent proposal count.
- A finite-bound logit chart can increase useful residual-decreasing proposals
  while preserving strict interior bounds and the canonical validation boundary.

## Result

- Zero-count precision bucket normalization removed all 2,625 historical false
  precision mismatches.  Candidate-local representation gating makes adapted
  CPQR conformant: 144/1,008 valid refinement seeds, 270 unsupported seeds,
  zero safety emissions, zero proposal disagreements, and one route/work-only
  disagreement.  This is a positive mechanism signal, not production evidence.
- Weak bracket and weak-then-adaptive remain representation-limited.  The
  successor does not conceal their 11 proposal and 18 route disagreements.
- On the 18 generated case / 72 trial-per-arm S0, direct and charted weak-pair
  arms had zero precision mismatches, zero proposal-count representation
  disagreements, and zero answer/refinement-seed safety emissions.  The charted
  arm produced 69 residual-improving starts versus 42 direct at equal 120
  callbacks.  Six safety-control trials activated each proposal arm; those
  outputs remain unpromoted starts and must pass the unchanged canonical path.

## Disposition

- Advance adapted CPQR and the charted weak-pair start generator to a real
  compiled development screen as separate ablations.
- Do not advance weak-then-adaptive unchanged.  Reopen it only with a stable
  representation of the weak subspace or a representation-invariant subspace
  sampling rule.
- Do not connect any S0 output directly to answer production.  Baseline search
  quota and canonical 512/768-bit replay remain mandatory.

