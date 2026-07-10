# Requirement Traceability

CI validates this table mechanically once the bootstrap checker lands. `Owner`
is a component owner, not a person-specific permanent assignment.

| Requirement group | Milestones | Verification | Owner |
|---|---|---|---|
| GOAL-01..05 | M3-M9 | family-disjoint anytime benchmark and Miss Analyzer | Core/Search |
| GOAL-06 | M0-M10 | architecture fitness, review and drift report | Root |
| DSL-01..09 | M1, M2, M7 | ABI conformance, differential and external-plugin tests | Base/SDK |
| ANS-01..08 | M1, M3, M6, M8 | schema, replay, guard, interval and exact-proof tests | Verification |
| ARCH-01..08 | M0-M3 | dependency and architecture fitness tests | Root/Core |
| RES-01..06 | M0, M3-M9 | experiment-card and benchmark-manifest checks | Research |
| QA-01..03 | M0-M10 | PR/nightly/weekly/release CI tiers | QA |

## Milestone chain

| Milestone | Deliverable | Exit condition |
|---|---|---|
| M-1 | Independent clean repository | `main`, no remote, no imported legacy code/history, root checkpoint. |
| M0 | Governance and reproducible toolchain | Charter, requirements, ADRs, research protocol, pinned Julia/Python, CI smoke green. |
| M1 | Plugin ABI vertical slice | Opaque custom call, branch Choice, strict guard, C0 and exact-capable example pass end-to-end. |
| M2 | Canonical compiler/oracle | Reference differential mismatch 0; compiler performance experiment completed. |
| M3 | Research-ready baseline | Single event/store/log, deterministic replay, full-support baseline, Miss Analyzer. |
| M4 | Local solve and scaling | Fixed-start factorial study; robust promoted champion or minimal baseline retained. |
| M5 | Discovery/archive/scheduler | Separate paired ablations and fair anytime coordinator. |
| M6 | Branch/guard/singular/unbounded | Critical failure-family suites and continuous-image detection pass. |
| M7 | Built-ins and SDK | Required primitives migrated; an external plugin can be authored from public docs. |
| M8 | High precision and exactness | Config validity and target identity certificates replay independently. |
| M9 | Generalization loop | Frozen 95/90/95 gates and all safety gates pass. |
| M10 | Hardening/release | Isolation, parallel/replay, cross-platform, soak, beta and four-week RC complete. |

Every milestone records artifacts, quantitative results and a rollback point.
Failure to pass a gate reverts to the prior champion; gates are never loosened to
promote an implementation.

## Current RES-03 evidence

The M3 Miss Analyzer has an implemented v0.1 vertical slice: strict diagnostic
and report schemas, a deterministic API/CLI, conservative adapters for current
event/checkpoint `Observation` diagnostics, and counterexample/metamorphic
tests. Coverage and deliberately unknown paths are recorded in
`docs/research/MISS_ANALYZER.md`. RES-03 remains active and M3 is not declared
complete here: automatic capture instrumentation, archive/scheduler causal
audits and the listed unclassified paths still require later milestone work.
