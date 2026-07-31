# Root-only portal Repair A invocation

Use `arm.json` with the existing Root-custodied screen24 launcher.  The frozen
full entrypoint is `portal_worker.py` (SHA-256
`6210280ed43e0c66b6f079d7e98bb82b68d2d899eddd5600020b92a9e8c87bef`).
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
case outcome, target, or truth.  The portal is inferred after the first three
baseline starts and replaces only ordinal three.  The portal route consumes at
most 25% of the callback cap; baseline may resume at ordinal four with the
remaining fixed 75% baseline callback allowance.  Thus all 64 period-four
product-Cauchy insurance ordinals at 256 starts remain baseline.  If the local
pool is UNKNOWN, ordinal three onward continues with the unchanged prefix,
kernel, and original callback cap.
