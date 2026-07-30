# EXP-STRUCT-POLY-001

Generated Wave 2 prototype combining `EXP-STRUCT-001` block decomposition with
the unchanged strict gate and bounded solver from `EXP-POLY-001`.

Run with the pinned Python/SymPy environment:

```bash
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  -m unittest -v test_btf_polynomial_pipeline.py
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python run_s0.py
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
