# EXP-EVAL-001: append-aware reservoir and cached sparsity

Status: S0 implemented; formal S1 is owned by the root benchmark process.

## Incremental continuation mechanism

The pinned continuation checkpoint binds the complete `search.endpoints` and
dynamic work record. Appending endpoints therefore invalidates the checkpoint
and replays every old endpoint in every continuation window.

`incremental_reservoir.py` stores the source-bound semantic observations plus
the exact covered endpoint prefix. On append it:

1. validates the content digest, source SHA, immutable search-plan SHA, covered
   count and exact canonical endpoint prefix;
2. reuses only previously source-verified observations;
3. replays the old deadline backlog, previously unobserved ordinals and the
   newly appended suffix, so transient failures are never permanently dropped;
4. rebuilds the original reservoir plan from the combined observations; and
5. atomically writes the next complete checkpoint.

Any schema/source/plan/prefix mismatch is a full-replay cache miss. Corrupt v2
content raises and fails closed. The overlay does not cache answers, HP results
or exact descriptors and does not modify canonical authority.

For a candidate built from pinned product code, add this directory to
`PYTHONPATH`, import `continuation_overlay`, and call
`continuation_overlay.install(geotarget.continuation)` before continuation.
`install_initial_checkpoint` may additionally replace the initial reservoir
writer so the first continuation window can consume v2 directly. A legacy v1
checkpoint remains safe: it causes one full replay and is then upgraded.

## Independent cached-sparsity ablation

`cached_sparsity.py` is not combined with the reservoir candidate. It caches a
truth-blind AST dependency/coloring plan by canonical semantic document and
uses colored forward differences only when the predicted direction saving is
at least 20%. Unknown dependencies become dense. Non-differentiable/selector
operations, guard branches, shape/nonfinite errors and changed branch traces
use the unchanged dense finite-difference path.

This explicitly satisfies the reopen condition of the earlier colored-FD
negative result: cached compilation plus applicability gating. It remains an
S0 ablation until the benchmark owner decides whether its activation breadth
justifies wiring it into a champion local-solver candidate.

## Reproduction

Run with the frozen Python environment:

```text
/home/kabatan/work/solver/.venv/bin/python -m pytest -q \
  test_incremental_reservoir.py test_cached_sparsity.py
/home/kabatan/work/solver/.venv/bin/python frozen_differential.py \
  --probes 725 --windows 5
```

The recorded run produced 2,175 bit-identical frozen candidate comparisons,
zero mismatches, a 66.7% semantic-replay reduction, 1.15x wall speedup and zero
unexpected fallback. The cached-sparsity synthetic route reduced four dense
directions to two and demonstrated all declared fail-closed fallbacks. No
validation, sealed corpus, truth file, screen24 or heavy HP benchmark was read
or run.
