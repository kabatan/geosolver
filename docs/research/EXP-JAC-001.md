# EXP-JAC-001 — sparse finite-difference coloring

EXP-JAC-001 was executed from the frozen preregistration and rejected at the
development gate. Production remains on dense central finite differences; the
family-disjoint locked artifact was not opened.

## Causal record

- Harness and mechanical gate: commit `09da3ce`.
- Seed-count interpretation fixed before outcomes: commit `afdf28d`.
- Development and locked inputs frozen before outcomes: commit `32f164d`.
- Raw development outcomes: commit
  `7f74d1550b0f04d40fb56e521e43e438e443fb1c`.
- Canonical summary:
  `research/results/EXP-JAC-001/summary.json`.
- Replay checksums:
  `research/results/EXP-JAC-001/artifact-checksums.json`.

The development grid contains ten typed construction graphs and 32 fixed starts
per graph. The compiler alone supplied every Jacobian sparsity entry. Before
local solves, J1 was compared with frozen dense Jacobians at all 320 starts.
The test-only incomplete pattern was detected on all 10 cases, and forced group
failure retried every affected column in all three family controls.

## Result

| Measurement | Result | Gate |
|---|---:|---:|
| Dense/colored mismatches | 0 | 0 required |
| Nonzeros outside compiler pattern | 0 | 0 required |
| False candidates | 0 | 0 required |
| Budget overruns | 0 | 0 required |
| J0 / J1 `P_local_gold` | 1.000 / 1.000 | loss ≤ 0.02 |
| Sparse oracle-work reduction | 0.4381 | ≥ 0.20 |
| Family-clustered one-sided 95% lower bound | 0.2839 | > 0 |
| Dense warm overhead | 0.1478 | ≤ 0.05 |
| Maximum cold coloring fraction of 32-start run | 0.2548 | < 0.01 |

J1 therefore demonstrated a real sparse-work benefit without a semantic or
recall regression, but it failed both overhead requirements. The dense-overhead
kill criterion fired without a recall gain. Natural coloring matched the
registered lower bound in the block and banded families; its family-mean gap
did not exceed 20% in three families, so J2 was not run.

## Consequence

The negative result is about the current general-default mechanism, not about
the correctness of compiler-derived coloring. A future experiment may test
compile-time caching or a compiler-only applicability predicate, but it must
retain full dense differential testing, explicit group-fallback accounting and
the same canonical endpoint replay. It cannot reuse or inspect the frozen
locked set unless a new preregistered development gate first passes.
