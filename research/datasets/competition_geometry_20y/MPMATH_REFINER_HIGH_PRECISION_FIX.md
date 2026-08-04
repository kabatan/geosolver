# High-precision refinement fix

## Scope

This change repairs the high-precision path used by the audited geometry
benchmark.  No DSL JSON, source statement, guard, target answer, or
presentation post-processing was changed.

The experiment branch deliberately runs the separately frozen runtime at
`/home/kabatan/work/solver-experiment-runtime`.  The implementation is in
`geosolver/src/geosolver/_internal/pipeline/refine/mpmath_refiner.py` in that
runtime; the regression tests are in
`geosolver/tests/regression/precision/test_mpmath_refiner_closure_gate.py`.

## Bugs repaired

1. The `direct_evaluation` shortcut used to return immediately after a
   `1e-15` residual check.  That check is only a numerical gate, so it could
   bypass all exactification work.  A direct candidate now gets closure polish
   first and falls through to the existing staged LM path if closure is not
   certified.  The LM path keeps its best iterate and hard-feasibility filter.

2. `findroot` was treated as successful without checking its final residual.
   The closure now returns a result only when the original high-precision
   evaluator meets the requested target; a small `findroot` step alone is not
   sufficient.

3. A one-variable problem with several constraints used only residual index
   zero during closure.  Fixed constraints could therefore make closure a
   no-op.  All residuals are now passed through mpmath's overdetermined
   one-variable Newton path, and matrix roots are normalized safely.

4. Two common zero predicates have nonsmooth derivatives at the exact root:
   point-point `Distance(P,Q)=0` and line-circle `IsTangent(...)=0`.  During
   local high-precision optimization only, they are represented by equivalent
   smooth zero-set residuals (`dx,dy` and signed squared distance minus
   `r**2`).  The original evaluator is still used for final certification, so
   the problem meaning is unchanged.

5. Closure iteration limits are scaled with the requested precision, and a
   certified closure at a higher precision is allowed to promote even when a
   lower-precision residual was rounded to the same displayed zero.  This
   prevents a 120-dps closure from blocking the 250/350/500-dps refinement
   needed by exact identification.

## Evidence

The focused benchmark used seed `7`, `--budget 180`, `--jobs 1`,
`taskset -c 0`, and `--require-one-core`.

| case | before strict exact | after strict exact | after answer value |
|---|---:|---:|---|
| AIME-2006-I-07 | no | yes | `408` |
| HMMT-2006-FEB-GEO-01 | no | yes | `sqrt(2) + 20` |
| HMMT-2014-FEB-GEO-08 | no | yes | `600/73` |

The before run was `0/3` exact; the final run was `3/3` exact.  The final
wall times were 1.25 s, 47.30 s, and 3.46 s respectively, all within the
180-second budget on one core.  Strict comparison was against the independent
`exact_truth.jsonl` ledger, not a decimal tolerance or a presentation
post-process.

Validation results:

- frozen runtime regression suite: **128 passed, 1 skipped**;
- new closure/refinement regression file: **6 passed**;
- Ruff on both modified runtime/test files: **clean**.

The final modified runtime SHA-256 is
`0d29248086229239c1bc160b56fc38b7c21aa0c11e943416add63ee9e3411dd0`.
The optional closure failure guard also treats mpmath `TypeError`/`IndexError`
as an unproven closure instead of aborting the solver.
