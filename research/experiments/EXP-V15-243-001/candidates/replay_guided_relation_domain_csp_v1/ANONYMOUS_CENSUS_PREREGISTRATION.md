# Relation-domain CSP anonymous degree-1 census

This root-owned census uses the frozen 85-row anonymous degree-1 source panel
only as a source projection corpus.  The endpoint and degree-1 proposal
relation in the request manifest are never passed to the candidate and cannot
route, prune, or order proposals.  No truth, score, prior outcome, problem ID,
or known target count is present or read.

Each row runs in a fresh Python process under the hash-pinned root-scoped
subprocess guard.  Fixed per-row caps are 3.0 seconds wall, 512 MiB root and
process-group RSS, 2 GiB address space, 1.5 GiB data, and 16 KiB combined
stdout/stderr.  Raw row and process artifacts remain under the root-owned
repository-external output; stdout and `AGGREGATE.json` contain counts only.

The census passes only with at least three full-replay-ready sources spanning
at least three target-blind structural signatures, and zero malformed/resource
rows, selection/truth violations, or authority/release violations.  A pass is
only `GO_HEADROOM_REVIEW_HOLD`; formal authority and target release remain
false and a benchmark-owner headroom review is still required.

## Exact prepared command — do not run without CPU14 custody

```bash
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
timeout --signal=TERM --kill-after=5s 300s \
taskset -c 14 /home/kabatan/work/solver/.venv/bin/python \
  run_anonymous_census.py \
  --requests /home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-requests.json \
  --requests-sha256 ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35 \
  --output-root /home/kabatan/work/solver-experiment-results/relation-domain-csp-degree1-census-v1 \
  --cpu 14
```

Expected elapsed time is 30–90 seconds; the preregistered worst-case row-wall
sum is 255 seconds and the outer hard wall is 300 seconds.  This command does
not import or invoke Julia, Nemo, HP, a global machine lock, a scorer, or a
formal authority.

## Frozen result

The root-owned one-shot run completed all 85 rows with process classification
`SUCCESS`.  Proposal-ready sources, proposals, and full-replay-ready sources
were all zero.  The aggregate failure taxonomy was
`SEMANTIC_LIFT_REJECTED=84` and
`PERIODIC_SOURCE_RECONSTRUCTION_NOT_IMPLEMENTED=1`.  Malformed/resource rows,
selection/truth violations, and authority/release violations were all zero.
Maximum observed row wall was 0.311 seconds and maximum process-group RSS was
58,535,936 bytes, below the fixed caps.

Decision: `STOP_ANONYMOUS_CENSUS`; no tuning or retry was performed.  The
repository-external aggregate SHA-256 is
`577608149bcd69375dd585f58ce0410194ea532bf1545d4c971437759bef4133`.
Reopen only with a new anonymous row that passes the existing target-blind
semantic lift, or a separately generated/reviewed exact semantic-lift
expansion; periodic support also requires a complete finite phase-sheet rule.
