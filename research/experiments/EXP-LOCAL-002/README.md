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

## Frozen development run

`development-input-manifest.json` freezes 48 development instances, 32 starts
per instance, replay material, and start checksums before execution. The grid
contains six instances from each benchmark family and covers every S1--S8
stratum at least six times.

Run the five variants in separate fresh Julia processes and aggregate the
8/16/32 prefixes with the repository's family-clustered paired bootstrap:

```powershell
python research/experiments/EXP-LOCAL-002/development_analysis.py
```

Completed raw attempts are compressed to `attempts.csv.gz`; the saved
bootstrap resample plans, checksums, aggregate CSV, paired confidence records,
environment, and mechanical development decisions are written under
`research/results/EXP-LOCAL-002/development-v0/`. A failed run leaves `.work`
files so it can be continued with `--resume`. The command refuses to overwrite
a completed result unless `--force` is supplied.

The development decision may freeze a candidate for later locked validation,
but cannot promote an algorithm or add a production dependency.
