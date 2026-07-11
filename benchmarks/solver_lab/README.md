# Solver Algorithm Lab

This is the deliberately thin bridge between the standalone analytic benchmark
families and the production Julia numerical kernel. It is for fast algorithm
screening, not for product claims or formal evidence.

The runner enforces one important separation: an algorithm receives a
`SolverExperimentCase` containing only black-box evaluation, bounds and numeric
scales. It does not receive family/instance IDs, Gold configurations, Gold
targets or the saved-start matrix. Gold is used only after each attempt for
independent scoring.

Run the current LM-QR control over one representative case from every family,
plus a four-configuration/two-target collision companion:

```powershell
julia +1.12.6 --startup-file=no --history-file=no --project=julia `
  benchmarks/solver_lab/run.jl
```

The default prefixes are 2/4/8 starts. Machine-readable output goes to the
ignored `benchmarks/results/raw/solver-lab-baseline.json`; stdout is only a
compact final-prefix table. A focused fast run is:

```powershell
julia +1.12.6 --startup-file=no --history-file=no --project=julia `
  benchmarks/solver_lab/run.jl `
  --families=TANGENT-CIRCLE-LINE,MULTIROOT-WARPED `
  --prefixes=2,4,8 `
  --output=benchmarks/results/raw/solver-lab-smoke.json
```

For paired algorithm experiments, construct the frozen local-only controls by
name (they deliberately do not include production root correction, target-image
analysis, or candidate validation):

```julia
controls = (
    core_lmqr_control(:legacy_lab_120x600),
    core_lmqr_control(:prod_tol_120x600),
    core_lmqr_control(:prod_options_250x2000),
)
```

The first preserves the historical 120/600 and `sqrt(eps(Float64))` baseline,
the second changes only the residual tolerance to `1e-12`, and the third uses
the nominal production local limits of 250/2000 with that tolerance. Each
variant manifest records the residual tolerance, initial damping, and finite
difference step explicitly.

## Adding a candidate

Construct another `SolverVariant` whose callable accepts `(case, start)` and
returns `SolverAttemptOutcome`, then pass baseline and candidate together to
`run_solver_experiment`. Use `evaluate_case(case, x)` for black-box values. Do
not close over a `DirectAnalyticProblem` or use benchmark truth in the variant.

```julia
candidate = SolverVariant("candidate-v1") do case, start
    # Run only on case evaluation/bounds/scales.
    SolverAttemptOutcome(start; status="example", evaluations=1)
end

run = run_solver_experiment(
    problems,
    [core_lmqr_variant(), candidate];
    prefixes=(8, 16, 32),
    evaluation_limit=600,
)
```

The recorded metrics deliberately separate:

- solver-reported convergence and acceptance;
- independently recomputed canonical validity;
- Gold configuration recall and distinct-target recall from consistent
  configuration witnesses;
- numerical target-only matches as a separate diagnostic, never as recall;
- all-target success;
- false residual-qualified candidates;
- repeated configuration hits and repeated target witnesses;
- runner-counted black-box evaluations, variant-reported evaluations and
  an enforced per-attempt evaluation budget; and
- cold-first-use versus warm wall time.

Compare evaluation/action budgets first. Wall time is diagnostic until variants
have been warmed in the same Julia process. Use direct analytic runs to reject
weak candidates quickly; confirm a survivor through the production
`ProblemSpecV1`/plugin/validation path before changing a public preset.
