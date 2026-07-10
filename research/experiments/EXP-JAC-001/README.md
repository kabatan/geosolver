# EXP-JAC-001 execution harness

This isolated harness executes the preregistered compiler-derived finite-
difference coloring experiment. The normal solver path remains dense; only an
explicit research call supplies `jacobian_entries` from `CompiledSparsity`.

The order is intentionally enforced:

1. Materialize typed graphs, fixed starts, analytic truth, compiler patterns,
   and dense Jacobian traces.
2. Compress and checksum both development and family-disjoint locked inputs.
3. Commit those inputs before any variant outcome is produced.
4. Run the dense/colored differential gate, then paired J0/J1 development.
5. Run J2 only when its preregistered structural color-gap trigger fires.
6. Inspect the locked artifact only if every development promotion criterion
   passes.

From the repository root, freeze inputs with:

```powershell
python research/experiments/EXP-JAC-001/prepare_inputs.py --partition all
```

After committing the frozen inputs, the development orchestrator is run with
`run_experiment.py`. Every callback, including unusable grouped probes,
individual fallback probes, trials, and canonical endpoint replay, is charged.
The result artifact records compiler/color construction, allocations,
factorizations, callback/oracle work, and cold/warm wall measurements.
