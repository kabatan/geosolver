# EXP-SINGULAR-001 S3 development result

This is a development advancement gate, not locked validation or product promotion.
Product connection: **false**.

| Variant | Eligible Gold | P_refinement_gold | Promoted | False | Callbacks | Precision-equivalent work |
|---|---:|---:|---:|---:|---:|---:|
| S1-AP-LMQR | 0/12 | 0.0 | 4 | 0 | 1209 | 5049 |
| S3-AP-BROYDEN | 0/12 | 0.0 | 0 | 0 | 2388 | 11292 |
| S3-ANALYTIC-SECANT-CONTROL | 0/12 | 0.0 | 0 | 0 | 1311 | 6327 |

Advancement decision: **stop after S3**.

- `analytic_control_decisions_match`: true
- `budget_limit_violations_zero`: true
- `candidate_control_recall_equal`: true
- `error_coverage_failures_zero`: true
- `false_promotions_zero`: true
- `metamorphic_disagreements_zero`: false
- `noneligible_s3_promotions_zero`: true
- `promoted_evidence_gate_failures_zero`: true
- `recall_gain_at_least_0_50`: false
- `s3_singular_recall_at_least_0_75`: false
- `semantic_replay_only_promotions_zero`: true

The result is bounded to exact stable-rank-deficient development endpoints. It does not certify general singular roots, open locked data, or connect S3 to production.
