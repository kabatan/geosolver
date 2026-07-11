# GeoTargetBenchmarks

`GeoTargetBenchmarks` is the standalone analytic laboratory for M0 local-solve
and discovery experiments. It depends only on Julia standard libraries and is
deliberately absent from the production `GeoTargetCore`/`GeoTargetGeometry`
dependency graph. Gold configurations are benchmark truth, never routing
features or solver starts.

Each `generate(params)` call returns a `DirectAnalyticProblem` containing:

- in-place canonical `residual!` and an optional in-place analytic `jacobian!`;
- a scalar target function, finite bounds, and declared variable/residual scales;
- independently constructed Gold configurations and distinct target
  descriptors (`ExactGoldTarget` or `ValidatedGoldTarget`);
- family/critical-stratum and requested/observed condition metadata; and
- fully materialized starts, transformations, coefficients, and Gold matrices.

Every materialized matrix has a platform-independent SHA-256 over explicit
little-endian Float64 bits. `replay_checksum(problem)` covers the complete
ordered artifact set, while `verify_replay_material(problem)` detects mutation.
A seed by itself is therefore never accepted as a replay record.

## Parameterized families

| Family | Controlled stress |
| --- | --- |
| `ScaleLadderParams` | Dimension and residual row-scale spread |
| `CurvedChainParams` | Dimension and narrow curved-chain strength |
| `NearRankDeficientParams` | Dimension, singular-value ratio, and materialized random orientations |
| `RedundantOverdeterminedParams` | Redundancy and near-dependency perturbation |
| `TangentCircleLineParams` | Closed-form root separation and tangency conditioning |
| `MultiRootWarpedParams` | Dimension, root count/separation, warp, row condition, and target collisions |
| `StrictGuardBoundaryParams` | Strict margins that are well separated, positive near zero, or exactly on the excluded boundary |
| `OpaqueTranscendentalParams` | C0-only Float64 callbacks with loops, control flow, and transcendental calls |

The compact D2 seed artifact is
`../../benchmarks/generated/m0-analytic-seed-manifest.json`. Regenerate its
exact contents with:

```powershell
julia --startup-file=no --project=julia/GeoTargetBenchmarks `
  julia/GeoTargetBenchmarks/scripts/render_m0_seed_manifest.jl
```

The manifest contains twenty fixed-seed S4 instances and twenty fixed-seed S6
instances in addition to the original analytic controls. Invalid strict-boundary
roots are materialized but excluded from Gold targets, and the opaque family
materializes its C0-only capability contract. The resulting development
manifest exercises all S1-S8 critical strata without turning diagnostic cases
into production support claims.

## Verification

```powershell
julia --startup-file=no --project=julia/GeoTargetBenchmarks `
  -e "using Pkg; Pkg.test()"
```

Tests independently evaluate every declared root, central-difference every
analytic Jacobian at every root, distinguish target values from configuration
count, replay the generated manifest, and check that Gold truth cannot affect
saved-start generation or production routing APIs.

## Solver algorithm laboratory

The package also owns a dependency-light, truth-blind variant/metric API in
`src/solver_experiment.jl`. It still does not depend on `GeoTargetCore`; the
root-level [solver lab](../../benchmarks/solver_lab/README.md) supplies the thin
Core adapter and executable command. This keeps Gold scoring out of the solver
callback while avoiding a second production execution path.
