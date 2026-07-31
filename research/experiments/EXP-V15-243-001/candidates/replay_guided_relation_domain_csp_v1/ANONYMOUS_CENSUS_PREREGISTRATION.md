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
