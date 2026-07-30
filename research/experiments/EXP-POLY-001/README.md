# EXP-POLY-001

Generated-only prototype for a strict polynomial/Groebner proposal lane.

Run with the pinned experiment Python containing SymPy:

```bash
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  -m unittest -v test_polynomial_side_route.py
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python run_s0.py
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  audit_development_formulations.py /path/to/development145.jsonl \
  development-static-audit.json
```

The lane accepts only one-to-three-variable square systems whose construction
aliases and constraints are exact rational polynomials. It rejects calls,
geometry objects, branches, comparisons, floating literals, non-polynomial
division, and unknown symbols. Degree, term, coefficient, solution, and wall
caps fail closed. At least half of numerical starts remain baseline. Symbolic
roots are proposals and have no authority without the caller's unchanged
canonical verifier.

The development audit parser does not deserialize JSONL rows. It lexically
extracts only the top-level formulation value and skips all sibling values; IDs
are not retained or reported. The frozen audit found zero direct whole-system
activations, so this route remains closed until its recorded reopen gate is met.
