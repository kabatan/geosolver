# EXP-EXACT-001 — exact release campaign development scaffold

This experiment prepares the release-gate campaign for C3A exact answers.  It
does **not** open X1, materialize U4, or contain a formal result.  The fixtures
in `src/development_cases.jl` are development-only and must not be scored as
holdout evidence.

The experiment deliberately reuses the production `NemoExactBackend`, original
graph C3A replay, stored-answer verifier, and solver API.  Its adapter receives
only a compiled problem and run controls.  Family labels and development truth
stay in the generator/test layer and are never passed into runtime routing.

The outcome-unobserved design is locked in `preregistration.json`.  Before any
formal input is generated, the solver policy and scorer must be frozen in a
separate commit.  U4 is generated only after that freeze by an independent
plugin authoring step.  Development commands must not write under `formal/`,
`x1/`, or `u4/`.

Run the targeted suite with:

```sh
julia --project=research/experiments/EXP-EXACT-001 \
  -e 'using Pkg; Pkg.instantiate(); Pkg.test()'
```

