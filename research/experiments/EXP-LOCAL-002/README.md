# EXP-LOCAL-002 runner

This directory is an isolated research environment for the preregistered
`EXP-LOCAL-002` local-solver comparison. It does not add NonlinearSolve to the
production Julia environment.

Run the fixed non-gating pilot from the repository root:

```powershell
julia --project=research/experiments/EXP-LOCAL-002 `
  research/experiments/EXP-LOCAL-002/run_pilot.jl
```

The runner fixes eight materialized starts for each of eight representative
families and compares `NLS-LM`, `NLS-TR`, `NLS-RMN`, `NLS-TR-STRICT`, and the
in-house `LXR-LMQR`. Every external candidate receives the same explicit
central `AutoFiniteDiff` route, normalized bounds through
`NonlinearLeastSquaresProblem` `lb`/`ub`, declared residual scaling, and common
iteration/evaluation budgets.

Package return codes are diagnostics only. The runner independently replays
the endpoint and checks residuals, bounds, the S4 strict guard, normalized Gold
configuration distance, and target error. Results are written to
`research/results/EXP-LOCAL-002/pilot-v0/` as CSV, JSON, and Markdown. This pilot
is adapter validation and is never a promotion decision.
