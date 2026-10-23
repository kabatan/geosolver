"""Small exact illustrations, not performance experiments or new theorems.

Chebyshev k=1..8: degree, square-freeness, and exact real-root count.
Boolean encoding: every 3-literal clause on three variables, including repeats.
Always-feasible answer-set encoding: all subsets of the eight full clauses.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import resource
import sys
import time
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
START = time.monotonic()
import sympy as sp

OUT = Path(__file__).resolve().parent
x = sp.Symbol("x")
f = sp.Poly(x, x, domain=sp.ZZ)
cheb = []
for k in range(1, 9):
    t0 = time.monotonic()
    f = 2*f*f - sp.Poly(1, x, domain=sp.ZZ)
    deg = f.degree()
    squarefree = sp.gcd(f, f.diff()).degree() == 0
    count = int(f.count_roots(-1, 1))
    recurrence_identity = f == sp.Poly(sp.chebyshevt(2**k, x), x)
    assert deg == count == 2**k and squarefree and recurrence_identity
    cheb.append({"k": k, "circuit_quadratic_steps": k, "after_substitution_variables": 1,
        "expanded_degree": deg, "nonzero_terms": len(f.terms()),
        "max_abs_coefficient_bits": max(abs(int(c)).bit_length() for c in f.all_coeffs()),
        "exact_real_roots_in_minus1_1": count, "squarefree": squarefree,
        "chebyshev_identity": recurrence_identity, "seconds": time.monotonic()-t0})
with (OUT / "chebyshev-check.csv").open("w", newline="") as fp:
    w = csv.DictWriter(fp, fieldnames=list(cheb[0])); w.writeheader(); w.writerows(cheb)

def litval(lit, assignment):
    i, sign = lit
    return assignment[i] if sign else 1-assignment[i]

assignments = list(itertools.product((0, 1), repeat=3))
literals = list(itertools.product(range(3), (False, True)))
checked = 0
for clause in itertools.product(literals, repeat=3):
    for a in assignments:
        ls = [litval(l, a) for l in clause]
        y = (1-ls[0]) * (1-ls[1])
        encoded = y*(1-ls[2]) == 0
        boolean = any(ls)
        assert encoded == boolean
        checked += 1

# In the always-feasible version, z=0 is always permitted; z=1 is
# permitted exactly on satisfying assignments. Each y,t is uniquely forced.
clauses = [tuple((i, signs[i]) for i in range(3))
           for signs in itertools.product((False, True), repeat=3)]
formula_rows = []
for mask in range(1 << len(clauses)):
    selected = [c for j,c in enumerate(clauses) if mask & (1 << j)]
    sat = [a for a in assignments if all(any(litval(l, a) for l in c) for c in selected)]
    value_set = set()
    solution_count = 0
    for a in assignments:
        for z in (0,1):
            good = True
            for c in selected:
                ls = [litval(l,a) for l in c]
                y = (1-ls[0])*(1-ls[1])
                t = z*y
                good &= t*(1-ls[2]) == 0
            if good:
                value_set.add(z); solution_count += 1
    assert value_set == ({0,1} if sat else {0})
    assert solution_count == 8 + len(sat)
    formula_rows.append({"formula_mask": mask, "n_clauses": len(selected),
                         "satisfying_assignments": len(sat),
                         "always_feasible_solutions": solution_count,
                         "answer_set": sorted(value_set)})

# A symbolic check of the degree of each encoding row, independent of
# enumerating Boolean assignments. All variables are explicitly counted.
xx = sp.symbols("x0:3")
z,y,t = sp.symbols("z y t")
max_degree = 0
for c in itertools.product(literals, repeat=3):
    ls = [xx[i] if sign else 1-xx[i] for i,sign in c]
    eqs = [v*(1-v) for v in (*xx,z)]
    eqs += [y-(1-ls[0])*(1-ls[1]), t-z*y, t*(1-ls[2])]
    max_degree = max(max_degree, max(sp.Poly(q,*xx,z,y,t).total_degree() for q in eqs))
assert max_degree == 2

out = {"elapsed_seconds": time.monotonic()-START, "python": sys.executable,
       "sympy": sp.__version__, "chebyshev": cheb,
       "boolean_clause_assignment_checks": checked,
       "always_feasible_formula_checks": len(formula_rows),
       "all_equations_max_degree": max_degree,
       "always_feasible_unsatisfiable_examples": [r for r in formula_rows if r["satisfying_assignments"] == 0],
       "formula_results": formula_rows,
       "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       "scope": "Exact finite sanity checks of proofs; no solver/local search; not a complexity lower-bound experiment."}
(OUT / "theory-check.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k:v for k,v in out.items() if k != "formula_results"}, ensure_ascii=False, indent=2))
