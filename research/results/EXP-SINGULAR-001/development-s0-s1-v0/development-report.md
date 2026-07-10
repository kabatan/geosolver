# EXP-SINGULAR-001 S0/S1 development result

This is a development advancement gate, not locked validation or product promotion.
Product connection: **false**.

| Variant | Phase-A Gold | P_refinement_gold | Promoted | False | Callbacks | Precision-equivalent work |
|---|---:|---:|---:|---:|---:|---:|
| S0-POINT-REPLAY | 0/48 | 0.0 | 0 | 0 | 144 | 688 |
| S1-AP-LMQR | 48/48 | 1.0 | 48 | 0 | 5442 | 26204 |
| SLB-ANALYTIC-DERIVATIVES | 48/48 | 1.0 | 48 | 0 | 2616 | 11367 |

Advancement decision: **advance to S2**.

- `error_coverage_failures_zero`: true
- `false_promotions_zero`: true
- `metamorphic_disagreements_zero`: true
- `phase_a_gain_at_least_0_15`: true
- `phase_a_s1_recall_at_least_0_90`: true
- `semantic_replay_only_promotions_zero`: true

The S0 point replay remains diagnostic-only even when its residual gate accepts the fixed P1 endpoint.
