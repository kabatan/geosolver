# Duplicate audit

Verdict: `NOVEL_PROOF_OPERATION_WITH_EXISTING_SCHEDULER_OVERLAP`

The following prior mechanisms were inspected before implementation:

| Prior mechanism | Existing operation | Difference from this candidate |
|---|---|---|
| `cross_endpoint_hp_rungs` / `wave17_cross_endpoint_hp_rung_racing_g0` | FIFO/interleaved HP precision scheduling across immutable endpoints | It schedules endpoint-local exactification and never forms elementary symmetric sums across endpoints. |
| `cross_endpoint_hp_voi_racing_d0` (`b75145de`) | Progress/cost/censor-aware endpoint allocation | It changes work allocation, not the algebraic proposal language. |
| `EXP-MULTITARGET-001/species_racing.py` (`022763fd`) and Repair A (`689330f8`) | 75/25 descriptor-species allocation and dominance-safe union | It races already existing proposal routes; it does not reconstruct a shared polynomial from scalar values at multiple endpoints. |
| `adaptive_exact_coordinate_first_wave2` and individual HP/PSLQ lanes | Per-endpoint coordinate/minpoly recognition | They do not exploit cancellation in cross-endpoint elementary symmetric sums. |
| `known_root_line_circle_deflation` | Exact source-derived second root from a line, circle, and `exclude=P` | It requires a known source quadratic and known root.  This candidate uses neither source eliminant nor geometry primitive semantics. |

Thus scheduling, quota, and final replay are deliberately reused, while the
proof proposal `S -> (e_1(S),...,e_d(S)) -> Q[t]` is new.  No prior search of
the experiment history found `elementary symmetric`, `symmetric sums`, or a
Vieta rational-reconstruction implementation over an HP endpoint set.

The new operation remains proposal-only.  It cannot certify that the observed
set is complete, and it sets `completeness_claimed=false`; every associated
full tuple must independently pass the existing canonical verifier.
