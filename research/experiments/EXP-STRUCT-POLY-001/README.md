# EXP-STRUCT-POLY-001

Generated Wave 2 prototype combining `EXP-STRUCT-001` block decomposition with
the unchanged strict gate and bounded solver from `EXP-POLY-001`.

Run with the pinned Python/SymPy environment:

```bash
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  -m unittest -v test_btf_polynomial_pipeline.py
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python run_s0.py
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  run_full_v15_activation_smoke.py
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  run_leftover_trace_smoke.py
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  audit_development_formulations.py /path/to/development145.jsonl \
  development-static-audit.json
```

The pipeline first computes a perfect-matching/SCC BTF plan. It projects exact
source constraints and transitively required aliases for each block without
rewriting expressions. Every projected block is independently rechecked by the
strict `QQ` polynomial gate. References to predecessor/outside variables,
geometry calls, branches, excessive degree/terms/dimension, and malformed
source fail closed.

Roots only replace their block coordinates in an existing numerical template.
The resulting full-dimensional proposal has no authority until the unchanged
canonical verifier accepts it. At least half of starts remain baseline (75% by
default), and every route failure reclaims all starts for baseline.

`worker.py` is the common-arm entrypoint for the frozen full-v15 champion. It
does not subtract any baseline search starts or callbacks. For combined-
applicable formulations it appends at most 32 proposals after every original
endpoint and before the existing fresh source/guard replay. The side generator
has one two-second envelope and at most four symbolic blocks. Non-applicable or
parse-unsupported formulations are `exec`-delegated to the frozen worker with
the original argument vector, producing bit-identical dry output.

`arm-v2.json` and `worker_v2.py` supersede the proposal-only v1 arm for any
further screen. The v2 overlay calls the original fresh replay and every
baseline HP/restoration wave first, without parsing endpoints or inserting a
side proposal into a capped baseline reservoir. It activates only when the
original statistics report every discovered primary served, all waves
complete, no deferred primary, no unexamined backlog, and enough wall time for
generation, source replay, one original HP slot, and finalization. Incomplete
baseline service, no leftover slot, or any side failure returns the exact
original baseline result object. Side candidates use a separate invocation of
the original source replay and HP service after the completion gate.
