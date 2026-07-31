# Frozen aggregate-only real static census

The root-owned producer supplies one sanitized record per source using exactly
the fields whitelisted in `static_census.py`.  No ID, family, path, source
hash, polynomial, target value, truth, outcome, or individual disposition is
accepted.  The runner emits only input/eligible/ineligible counts, the number
of distinct mechanical eligibility signatures, and the fixed gate result.

Eligibility requires all of the following before the fixed caps are applied:

- complete reversible QQ semantic cover and exact raw-target AST;
- complete predicate ledger;
- an available producer that can prove the global upper identity;
- every specialized target fibre already proved finite;
- an ordered-field exact sign implementation is available.

The fixed caps are source variables 3, cover variables 8, equations 12,
degree 6, terms 512, coefficient bits 2048, predicates 3, global upper degree
16, target roots 16, target-factor degree 4, and quotient dimension 24.

Advance only for at least four eligible sources in at least two mechanical
signatures.  Census output always has `authority=false` and `release=false`.
It is not a real execution permit and must be written outside the repository.

Frozen invocation (run later by the benchmark owner when CPU 14 is free):

```bash
taskset -c 14 /home/kabatan/work/solver/.venv/bin/python \
  static_census.py \
  --panel /ROOT_OWNED/SANITIZED_THOM_HERMITE_PANEL.json \
  --output /REPO_EXTERNAL/thom-hermite-static-counts.json
```
