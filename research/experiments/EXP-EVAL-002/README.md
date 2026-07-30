# EXP-EVAL-002: cached sparsity full-v15 seam audit

Status: **BLOCKED_BEFORE_FORMAL_ARM**.

This is a separate audit of the cached-sparsity S0 mechanism. It is not mixed
with EXP-EVAL-001's incremental reservoir and has no `arm.json`: creating one
would claim a safe full-v15 mechanism which the current evidence does not
support.

The exact numerical hook is the unsupported-row dense finite-difference loop
in the frozen analytic/FD hybrid `_hybrid_jacobian`. Both retained and strict
restart tracks share that module object. The hook nevertheless cannot be
safely activated from the current source-AST plan:

- the real augmented Jacobian includes relation, guard, and opaque
  hard-feasibility rows, while the cached plan certifies relation rows only;
- the parent optimized wrapper cannot patch the separately launched one-core
  or pool search subprocesses;
- runtime branch fallback spends colored callbacks before dense replay and
  therefore cannot restore the original callback/work prefix; and
- bound-directed negative steps expose signed-zero bit differences in the
  current zero-fill reconstruction.

The source-only compiler was tightened so lowercase nondifferentiable calls,
AST branches, and opaque calls fail closed before coloring. Generated
positive-step block systems and variable/residual permutations remain bitwise
identical to dense FD, but that does not close the augmented-row, process, and
callback-accounting gaps above.

This also leaves the repository's prior reopen gate closed. Cached source-AST
analysis is not the compiled typed/effect dependency metadata requested by the
negative colored-FD and Wave-12 ledgers, and it does not change the measured
augmented-evaluator cost model. Repeating a formal screen would therefore
retest an exhausted mechanism before solving its recorded failure cause.

Reopen only after a typed/effect-certified DAG supplies complete dependencies
for relation, guard, and hard-feasibility outputs, or an equivalent branch
trace exists before a colored callback. Candidate-owned single-core and pool
entrypoints must then install the same hash-bound hook, and full-Jacobian
`uint64` equality (including signed zero and NaN payloads) must precede any
formal arm or worker smoke.

No problem truth, scorer, validation/sealed partition, formal screen, full
worker arm, or heavy HP route is used by this audit.
