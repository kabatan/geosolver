# EXP-COMP-001 typed-plan control benchmark

This microbenchmark compares the canonical reference interpreter with the M2
pre-resolved typed plan on the same open-world Geometry graph. The graph contains
two variables, constructed points and a line, one relation, one guard, one domain
margin and a scalar target. It records compile latency/allocation and warm scalar
and batch latency/allocation separately.

Run it from the repository root with the pinned Julia environment:

```powershell
julia +1.12.6 --startup-file=no --project=julia benchmarks/micro/compiler/run.jl 1000
```

The optional positive integer is the requested scalar evaluation count. Batch
rows are capped at 256 and repeated until at least that many evaluations have
run. Each batch matrix uses one sample per row and one variable per column.

This is an exploratory control, not a CI performance gate. Compare multiple
fresh-process runs on the same machine and Julia build; do not interpret a single
run as a promotion decision. Semantic equality is checked before timings begin,
and final solver acceptance must still use canonical replay.
