# SOURCE_QUADRATIC_MOMENT_ROUND_V1 static readiness

Decision at this stage: **scanner frozen; implementation remains gated**.

The candidate reuses the pinned `semantic_algebraic_lift` compiler only as a
source-order partial frontend.  The scanner rejects any source carrying a
target, post-process, identity, outcome, or truth field.  It injects the
constant target zero inside the compiler adapter and removes the synthetic
target auxiliary and target-link row before classification.

Only exact QQ equality rows of total degree at most two are eligible for the
future Shor moment matrix.  Unsupported and higher-degree source rows remain
mandatory for the later untouched local-tail/canonical replay, but are not
converted into moment constraints.  Strict, nonzero, selector, branch, and
definedness predicates are replay-only.  No epsilon closure or RLT/product
inequality is introduced.

For a readiness result, every selected semantic auxiliary must have all of its
QQ degree-at-most-two definition rows in the same source-connected cover.
Repair A adds a block-coordinate mapping rather than relaxing any polynomial
threshold.  A source variable incident to the quadratic component maps to a
direct stable lift index or finite-sheet phase pair.  A source variable outside
that component maps to `baseline_passthrough`: the later rounder must copy that
coordinate exactly from the existing search endpoint while replacing only the
moment-connected slice.  At least one source coordinate must be incident to a
selected quadratic component, and at least one selected equality must be
quadratic.  The scanner itself still reads no endpoint.  It emits no path,
source SHA, target, endpoint, case identity, or individual result file.

Generated checks pass for direct quadratics, disconnected source blocks,
sqrt auxiliary closure, and finite phase reconstruction.  They reject a
present target, degree-three-only system, unused source variable, non-QQ-only
system, and linear-only system.

The initial all-coordinate mapping found 42/135 ready sources but failed the
root-owned fixed gate at `NO_SEARCH=0/3`, `WITHOUT_SAFE_HP=1/6`.  No individual
fixed-panel record was returned.  After Repair A, the aggregate-only scanner
found 82 structurally ready sources on the same 135-source anonymous panel
(`a49f6e76...c5219`) and retained no individual record:

```text
ready                         82 / 135
quadratic-row-count absent    45
non-QQ-only                    8
```

This is a capability upper bound, not an outcome or recall measurement.  The
candidate must stop unless the separately frozen group panels satisfy all of:

- `NO_SEARCH_ENDPOINT >= 1`;
- `WITHOUT_SAFE_HP >= 2`;
- total ready intersection `>= 3`;
- support occurs across at least two independent request-manifest hashes.

The candidate agent does not inspect those group panels or their per-source
records.  The benchmark owner runs the frozen aggregate entrypoint and returns
only aggregate counts.

Reproduction uses CPU14 and Python 3.12.11:

```bash
taskset -c 14 env \
  PYTHONPATH=/home/kabatan/miniforge3/envs/py312/lib/python3.12/site-packages \
  /home/kabatan/.local/share/uv/python/cpython-3.12.11-linux-x86_64-gnu/bin/python3.12 \
  research/experiments/EXP-V15-243-001/candidates/source_quadratic_moment_round_v1/run_generated.py
```
