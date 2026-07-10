# EXP-SINGULAR-001 S4 development closure

Status: **bounded negative; stop before locked validation**.

The authoritative decision is the independently reconstructed
`independent-analysis.json`, bound by `independent-analysis-a10-bindings.json`
and protocol amendment A10. The frozen `summary.json` and `report.md` are
retained as immutable run artifacts but are not authoritative: their Julia
assessor narrowed Gold targets to `Float64` and incorrectly classified four S1
regular-fold promotions as successful.

Those four rows are protocol-level false promotions because their claimed
`1e-36`-scale target-error coverage cannot be checked against Float64-generated
Gold. This does not establish that S1 converged to the wrong geometric root;
it establishes that the frozen Gold/assessor precision is insufficient for
that coverage claim. The S4 stop decision below does not depend on this issue:
11/15 recall and four S4 metamorphic disagreement groups independently fail.

Exact independent reconstruction found:

- S4 candidate and analytic control each recovered 11/15 eligible endpoints;
- their per-case decisions were identical and neither had a false promotion;
- neither promoted any manifold, nonroot, higher-depth or regular-close-root
  control;
- both disagreed across representations in the same four deflation-one groups,
  with the orthogonal representation failing the final applicability audit;
- the frozen 12/15 recall and zero-metamorphic-disagreement gates therefore
  failed.

This result supports continued research on representation-stable two-step
singular refinement, but it does not establish a certificate, locked-set
performance, all-root completeness, a hard adversarial timeout or a production
route. Locked inputs remain unmaterialized and S4 remains disconnected from the
solver product.
