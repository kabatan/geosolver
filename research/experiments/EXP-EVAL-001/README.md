# EXP-EVAL-001: append-aware reservoir and cached sparsity

Status: S0 implemented and connected to the frozen full-v15 worker; formal S1
remains owned by the root benchmark process.

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
If the frozen search produced no accepted `search.json`, the initial writer
preserves the original result without a checkpoint instead of turning a search
miss into a worker crash.

`worker.py` imports the clean `0967ff1c` product modules, binds their relative
runtime paths to the separately restored frozen runtime, and invokes the pinned
`optimized_entrypoint`. The dry/execute plan protocol, final v15 result schema,
HP bridge, and canonical exact authority remain unchanged. Only continuation's
reservoir reconstruction seam is overlaid; a truth-free sidecar records whether
the incremental path actually activated.

## Independent cached-sparsity ablation

`cached_sparsity.py` is not combined with the reservoir candidate. It caches a
truth-blind AST dependency/coloring plan by canonical semantic document and
uses colored forward differences only when the predicted direction saving is
at least 20%. Unknown dependencies become dense. Non-differentiable/selector
operations, guard branches, shape/nonfinite errors and changed branch traces
use the unchanged dense finite-difference path.

This tests the proposed cached-compilation plus applicability-gating reopen
condition of the earlier colored-FD negative result. It remains an S0
ablation; the full seam audit found that source-AST caching alone does not
satisfy the stronger compiled typed/effect dependency gate.

The subsequent full-v15 seam audit in `../EXP-EVAL-002` blocked that wiring:
the current plan does not certify augmented guard/hard-feasibility rows,
runtime branch fallback is not callback-neutral, and a negative-step signed
zero counterexample violates the required bit identity. Lowercase
nondifferentiable calls, AST branches, and opaque calls are now rejected before
coloring, but no formal cached-sparsity arm exists.

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
validation, sealed corpus, truth file, formal screen24 or heavy HP benchmark was
read or run. A one-case truth-free worker smoke preserved the v15 schema and
activated prefix extension (6 verified records reused; 25 of 31 endpoints
replayed). The known `63fb3e...` missing-search regression also completed and
was accepted by the frozen runner predicate without a checkpoint crash.
