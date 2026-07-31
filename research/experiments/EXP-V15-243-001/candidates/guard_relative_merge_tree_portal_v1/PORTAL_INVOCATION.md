# Root-only portal Repair A invocation

Use `arm.json` with the existing Root-custodied screen24 launcher.  The frozen
full entrypoint is `portal_worker.py` (SHA-256
`576e6cf7b819c13c3a84bf6d445ef23c928cc597384058f574850b34e29dbce2`).
Run control and candidate at 5 seconds for seeds 0, 1, and 2 under the same
source manifest and isolated process policy.  Do not return per-case results
or source payloads to the candidate lane.

The corresponding direct search-seam form, useful only for Root diagnostics,
is:

```sh
taskset -c 14 env OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 \
  OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  PYTHONHASHSEED=0 /home/kabatan/work/solver/.venv/bin/python \
  /home/kabatan/work/solver-wt/guard-relative-merge-tree-portal/research/experiments/EXP-V15-243-001/candidates/guard_relative_merge_tree_portal_v1/portal_search_worker.py \
  --case "$SOURCE_JSON" --case-sha256 "$SOURCE_SHA256" \
  --arm precision_isolated_retained_then_strict_nearroot_restart_direct_broyden_ruiz_tr_lm \
  --seconds 5 --starts 256 --callbacks-per-start 600 \
  --aggregate-callback-cap 153600 --seed "$SEED" --output "$RESULT_JSON"
```

`$RESULT_JSON.guard-merge-portal.json` contains aggregate activation and the
search-result hash only.  It emits no observation point, residual, endpoint,
case outcome, target, or truth.  Repair A evaluates complete four-start
insurance blocks in original order and invokes the frozen structural selector
after each block.  It stops at the first portal, the fixed 75% baseline quota,
or deadline.  No original start is replaced.  The portal route consumes at
most 25% of the callback cap; remaining period-four insurance starts run first
inside the baseline continuation, followed by every other remaining prefix
start while quota remains.  If the local pool is UNKNOWN, the unchanged
prefix, kernel, and original full callback cap continue exactly.

The direct AB runner is `run_screen24_direct.py` SHA-256
`61bbe4ee8a254b311fa6dcddbe89d7e57d84c083512150383ed73f3621ae8867`.
It requires a nonexistent output root and aggregate path, strict manifest
leaves contained by the frozen input root, and a candidate sidecar whose digest
matches the exact `search.json`.  It cannot resume or reuse a pair directory.
Only aggregate safety and activation progress is printed every eight pairs.
