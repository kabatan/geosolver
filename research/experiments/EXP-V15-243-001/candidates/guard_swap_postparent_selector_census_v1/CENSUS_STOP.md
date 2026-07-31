# Census decision: STOP

The preregistered source-only census at commit `8545513e` was executed once on
CPU14 without the global benchmark lock.  The external aggregate is:

- path:
  `/home/kabatan/work/solver-experiment-results/guard-swap-postparent-selector-census-v1/AGGREGATE.json`
- SHA-256:
  `039e67343b1bc7f4dd830b73c723766478c2e995620ed602aa14e9f5a5071cc8`
- input closure SHA-256:
  `91bae98d0e9adbf89aeb9dfbfed8ebda5ecc37c52ea46ed45cc55a2d510decc6`

## Aggregate result

The frozen manifest passed its 36-job, two-arm-per-source, 18-distinct-source
checks.  All 18 fresh source workers returned containment classification
`SUCCESS`; worker/resource failures, target/truth/case/family/outcome reads,
authority, and release were all zero/false.  Peak process-group RSS was
141,819,904 bytes and maximum worker wall time was 1.021298 seconds under the
30-second/512-MiB group caps.

Ten sources had completed archived full-parent streams, yielding 246 unique
observations after paired-arm deduplication.  The source-only structural counts
were 15 square sources, three with complete analytic residual coverage, and
eight with at least one admitted smooth guard slot.

Exact old-mechanism eligibility was zero endpoints in zero sources and zero
typed guard signatures.  Aggregate rejection taxonomy was:

- source-valid: 56;
- residual above the frozen entry tolerance: 155;
- nonfinite: 8;
- exact pair-ineligible after the entry checks: 3; and
- observations belonging to statically ineligible sources: 24.

The fixed gate required at least four eligible sources and two typed guard
signatures.  Decision: `STOP_SELECTOR_CENSUS`.  No post-parent selector
prototype or parameter/lane tuning is authorized.

Reopen only with new anonymous full-parent observations or a separately
generated and reviewed source-DAG derivative expansion.  Loosening residual,
rank, slope, or guard tolerances, or selecting cases/lanes against these
results, is prohibited.  `authority_pass` and `target_release` remain false.
