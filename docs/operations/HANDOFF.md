# Maintainer Handoff

Updated: 2026-07-11 (Asia/Tokyo)
Checkpoint: `main` at `ab3866a` before this handoff-only commit

This is the restart boundary for the next maintainer. It is intentionally
shorter and more authoritative than the accumulated experiment history. The
solver is a research preview, not complete, and no completeness claim has been
made.

## Owner direction

The next work must prioritize the solver algorithm and measured fixed-budget
performance. Do not grow experiment-integrity infrastructure unless a small,
specific control is necessary to distinguish an algorithmic result.

Preserve these product invariants:

- the open-world Julia plugin ABI and Python geometry DSL;
- plugin-private, differentiable black-box operations that need not lower to
  coordinate polynomials;
- an anytime objective: maximize the probability of finding every distinct
  real scalar target value within a fixed budget;
- canonical replay and independent validation before an answer is promoted;
- `unknown`/`budget_exhausted`, never `no_solution`, when finite search ends.

The intended development loop is deliberately small:

1. measure the current solver on representative families, seeds and budgets;
2. classify misses, duplicates, false accepts and time allocation;
3. implement one mechanism behind an existing seam;
4. compare matched budget curves and retain it only when it helps;
5. keep the independent IID/full-support lane and black-box DSL route intact.

## Current implementation map

The end-to-end path already exists:

1. Python authoring: `python/src/geotarget/model.py` (`ProblemBuilder`).
2. Stable problem/plugin contracts: `julia/GeoTargetBase/src/problems.jl`,
   `plugins.jl` and `capabilities.jl`.
3. Registry and compilation: `julia/GeoTargetCore/src/registry.jl` and
   `compiler.jl` (`compile_problem`).
4. Black-box evaluation: `compiled_oracle.jl` (`evaluate` and
   `evaluate_canonical`).
5. Proposal scheduling: `proposal_engine.jl`, `search_policy.jl` and
   `search_loop.jl`.
6. Local numerical solve: `local_solver.jl` (`solve_local`, scaled LM/QR and
   finite-difference Jacobian seams).
7. Validation and distinct-target archive: `candidate_validation.jl`,
   `candidate_store.jl` and `target_image.jl`.
8. Public orchestration: `solver.jl` (`solve`).

The compact synthetic benchmark families are in
`julia/GeoTargetBenchmarks/src/`. The existing failure vocabulary is
`docs/research/FAILURES.md`; use only the telemetry needed for the current
comparison rather than extending every diagnostic category first.

There is not yet a compact end-to-end all-target recall runner. The existing
compiler microbenchmark is not a solver benchmark. Build the first runner as a
small development tool around the analytic families and their saved starts;
do not create another formal evidence system. Report configuration recall and
distinct-target recall separately. In particular, audit whether configurations
that map to the same target value survive public aggregation as duplicates.

## Frozen/deferred work

`EXP-LOCAL-003` is frozen as a result-blind protocol checkpoint. Formal C0,
C1 and C2 were never executed, no candidate result was observed, and no claim
file or formal evidence namespace was created. Do not run its formal launchers
as part of ordinary solver development.

A nonformal Windows AppContainer pilot reached Julia but failed while resolving
the active project with `SystemError: longpath: access denied`. Its broker
cleanup completed and left no formal evidence. Possible ACL/loader workarounds
were deliberately not pursued because they do not improve the solver. Revisit
this protocol only if a performant algorithmic finalist later needs a formal
promotion gate.

Historical `codex/*` branches are research archaeology. Their exact tips were
retained as annotated `archive/2026-07-11/*` tags and the branches were removed,
leaving `main` as the only branch. Do not merge an archive tag wholesale.
Inspect or cherry-pick an identified change only after checking that `main`
does not already contain an equivalent integrated version.

## Recommended restart

Start from a new `codex/` branch at this handoff commit. Before changing policy,
produce a lightweight baseline table over the existing benchmark families with
multiple seeds and at least three increasing time or evaluation budgets. Record
per-target recall, all-target success, false-answer count, duplicate work and
runtime. Then choose the largest observed failure class, not a preselected
algorithm name.

Likely low-cost seams for the first comparisons are proposal allocation and
refinement in `proposal_engine.jl`/`search_policy.jl`, local model/step control
in `local_solver.jl`, and exclusion or novelty policy at the candidate-store
boundary. Changes must consume only public numeric metadata and oracle calls;
they must not require polynomial extraction or benchmark truth at runtime.

Do not start with a Rust/Julia rewrite, another proof protocol, or broad
refactoring. The numerical core is already Julia. Refactor only around a
measured algorithm change, and keep a single production path after selection.

## Reproduction and checks

Environment contract:

```powershell
powershell -File scripts/doctor.ps1
```

The complete repository gate is:

```powershell
powershell -File scripts/ci.ps1
```

For a quicker repository smoke gate:

```powershell
powershell -File scripts/ci.ps1 -Tier Smoke
```

The complete gate includes long-running research and QA work. During the short
algorithm loop, run the directly affected Julia integration test plus the
benchmark package tests, then run the full gate before a release checkpoint.
Raw benchmark output belongs in ignored `benchmarks/results/raw/` paths.

Repository facts at handoff:

- the main worktree is clean after the handoff commit;
- no Git remote is configured;
- auxiliary worktrees were removed and historical branch tips were converted
  to annotated archive tags, leaving only `main`;
- local virtual environments may be retained, but generated test/cache
  directories are ignored and were cleared;
- the annotated tag `handoff-2026-07-11` names this restart point.
