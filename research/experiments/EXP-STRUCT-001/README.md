# EXP-STRUCT-001 — truth-blind block-triangular prototype

This is a deliberately rough, experiment-only prototype. It does not modify
the production solver or answer protocol.

The detector uses only the residual-variable incidence graph:

1. require a square system and find a structural perfect matching;
2. orient each matched equation from its input variables to its matched output;
3. compute strongly connected components;
4. topologically order the SCC condensation graph.

Two or more SCCs activate the block route. Non-square, structurally singular,
and irreducible systems fail closed to the numerical baseline. A fixed minimum
baseline quota is retained even when the block route activates. The staged
numerical code only proposes candidates; `solve_candidate` always calls the
supplied canonical verifier after routing and local solution.

The implementation does not inspect case IDs, problem names, target values, or
known answers. `analyze_development.py` obtains only the `formulation` member of
each development input record and emits aggregate statistics without case IDs.

Run the generated S0 tests and summary with:

```bash
cd research/experiments/EXP-STRUCT-001
python3 -m unittest -v test_block_structure.py
python3 run_s0.py
python3 analyze_development.py /path/to/development145.jsonl
```

The structural work metric is a factorization proxy, `sum(block_size^3) /
dimension^3`; it is not an oracle-work claim. Full compiled integration must
measure residual evaluations, evaluator work, and wall time under the common
benchmark harness before promotion.
