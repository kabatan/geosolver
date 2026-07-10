# EXP-LOCAL-003 C0 generator boundary

This directory contains result-blind source only. It does not contain a
materialized development input, a solver outcome, or the C2 scaling mechanism.

`generator.py::build_development_documents()` builds three independent in-memory
projections:

- `candidate`: 48 primary and 16 Safety cases containing only a full 64-hex
  `opaque_case_key`, Python-SDK `ProblemBuilder` document, 64 persisted
  calibration points, 32 starts, public numeric metadata and budgets;
- `assessor`: an unsealed generator-assessor projection (distinct from the
  formal closed assessor truth) with the matching key plus family/group/
  representation mapping, independent Gold configurations/targets and
  tolerances;
- `generator_private`: counter contracts and generator-only calibration/start
  keys.

Every problem travels through the public Python authoring model and canonical
encoder. The Julia `Local3FixturePlugin` is an allowlisted, otherwise unknown
plugin. Its codec-locked program literal and variadic scalar operations expose
only C0/Float64 value evaluation, including strict guard/domain roles. No
`DirectAnalyticProblem` enters this path.

`capture_calibration_truth.jl::capture_calibration_truth(candidate, assessor)`
independently decodes, freezes, compiles and evaluates all 4096 calibration
observations. It emits status/cost/z bits, `K`, nearest-rank `r`, clamped `a`,
fallback/clamp reasons and hashes. Before returning it rejects any primary
semantic-z/scale-permutation error or malformed Safety `Q*z` construction.

The command-line emitters are explicitly ephemeral integration helpers; none
writes a research input tree:

```powershell
$env:PYTHONPATH = (Resolve-Path python/src).Path
uv run --project python --frozen pytest research/experiments/EXP-LOCAL-003/source/test_generator.py
julia +1.12.6 --startup-file=no --history-file=no --project=julia research/experiments/EXP-LOCAL-003/source/test_plugin.jl
```
