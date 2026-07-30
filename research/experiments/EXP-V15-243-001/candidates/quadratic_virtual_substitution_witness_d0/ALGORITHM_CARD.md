# QUADRATIC_VIRTUAL_SUBSTITUTION_WITNESS — synthetic D0

- Hypothesis: a truth-blind min-fill elimination route can turn individually linear/quadratic rational systems into exact proof-bearing witnesses before the numerical baseline finds them.
- Mechanism: choose an equation-variable pair from the residual-variable graph, enumerate exact linear/quadratic branches, carry leading-coefficient, discriminant, denominator, and strict-guard conditions, cap branch states at 64, then replay the untouched source exactly. Endpoint values only order already verified configurations. Target descriptors are derived forward from the verified target value as a square-free minimal polynomial plus real-root ordinal.
- Scope: QF real polynomial/rational sources whose individual variable degrees are at most two. Unsupported degree, branch overflow, nonreal branch, zero denominator, or failed replay returns the baseline unchanged. The baseline retains 75% allocation and this side route receives at most 25%.
- Routing features: expression degrees, dependency fill, guard/denominator state, and branch count only. No problem, family, geometry, target truth, or case-success routing is present.
- Nearest failed mechanism / reopen condition: generic polynomial homotopy is not reopened; this is finite exact virtual substitution with source replay. Scaling or path-order tuning is not used.
- D0 corpus: 1,024 self-generated instances / 2,048 allocation traces, seed 20260731, comprising triangular, nontriangular, rational-guard, cubic-unsupported, branch-explosion, negative-discriminant, leading-zero, and zero-denominator families. Four variants cover variable permutation, residual permutation plus nonzero rational scaling, and CSE/factor rewrites.
- Result: 3/3 primary gain families; false authority 0; fallback mismatch 0; shared-baseline mismatch 0; metamorphic failure 0. All five negative/edge families either replayed an exact configuration or used exact fallback as specified.
- Decision: **ADVANCE** to truth-blind corpus screening. This result is synthetic-only and makes no 145/243 claim.

Reopen gate after a future rejection: only retry if failure traces show a degree-2 source for which branch accounting, condition propagation, or exact replay—not quotas, radii, seeds, or thresholds—lost a valid witness.
