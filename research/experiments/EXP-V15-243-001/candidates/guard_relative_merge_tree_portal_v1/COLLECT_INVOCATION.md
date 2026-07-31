# Root-only collect gate invocation

Run the frozen search seam directly for each source/seed; do not give the
candidate lane the source, result, or sidecar.  Replace the three shell
placeholders with Root-custodied paths/digest.

```sh
taskset -c 14 env OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 \
  OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  PYTHONHASHSEED=0 /home/kabatan/work/solver/.venv/bin/python \
  /home/kabatan/work/solver-wt/guard-relative-merge-tree-portal/research/experiments/EXP-V15-243-001/candidates/guard_relative_merge_tree_portal_v1/collect_search_worker.py \
  --case "$SOURCE_JSON" --case-sha256 "$SOURCE_SHA256" \
  --arm precision_isolated_retained_then_strict_nearroot_restart_direct_broyden_ruiz_tr_lm \
  --seconds 5 --starts 256 --callbacks-per-start 600 \
  --aggregate-callback-cap 153600 --seed "$SEED" --output "$RESULT_JSON"
```

The only new artifact is
`$RESULT_JSON.guard-merge-gate.json`.  It contains aggregate counts and hashes,
not observation rows.  The full common-control entrypoint for the existing
formal harness is `collect_worker.py` (SHA-256
`328985f035e6e46667dec8426643b2e10c0c7822d77e1662d6a13d9ddbfe56cf`).
Enable no portal proposal or 25% quota in this collection run.
