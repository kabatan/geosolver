# Solver improvement protocol — 2026-09-07

The 323-case corpus is development data. Every campaign uses the repository runner,
180 seconds per case, one physical core per job, and 16 jobs. Campaigns and heavy
profiling/tests do not overlap. Baseline and final use seeds 0, 1, 2; intermediate
comparisons use seed 0. Baseline source, DSL, configuration and dependencies are
frozen under `local-evaluation/solver-improvement-20260907/baseline-source` with a
SHA-256 manifest. Unrelated `algebra_v3` work is excluded from changes.

Correctness is exact answer-set equality. Report partial sets, extra answers,
errors/timeouts, total process time across *all* cases, solver time, common-solved
case time, median/p95, CPU, peak RSS and phase times. Keep per-case changes including
regressions. A source snapshot with `--allow-dirty` is an explicit development run,
not a claim of a clean engine-lock match. Keep the original frozen release.

Adoption gates: a loss of at most one percentage point requires at least 20% lower
total time; a time increase of at most 10% requires at least one percentage point
higher exact-match rate. Pareto improvements are acceptable when explained by a
general mechanism and supported by analytic families. Reject extra answers or
verification weakening regardless of speed. Completeness remains unknown.

`solver_improvement_families.py` fixes seed 20260907, six parameter draws per family,
and a family-level split before inspecting generated campaign outcomes. Tuning:
factored polynomials, closed endpoints, scaled linear systems, tangent polynomials.
Holdout: circle-line intersections, perpendicular bisectors, right-triangle lengths,
and reflected distances. Each has an analytically derived exact answer set. Each
original is paired with a fixed equivalent form: reverse equality order, multiply
equality residuals by -7, insert a redundant zero equality. The generator records
its own hash, parameters, derivations and split. Holdout outcomes are reserved for
the final candidate and are not used to choose thresholds or strategies.

Reproduction:

```sh
.venv/bin/python benchmarks/solver_improvement_families.py \
  benchmarks/local-evaluation/solver-improvement-20260907/generated
.venv/bin/python benchmarks/research_runner.py run OUTPUT \
  --jobs 16 --seeds 0,1,2 --allow-dirty
.venv/bin/python benchmarks/research_runner.py assess OUTPUT
.venv/bin/python benchmarks/research_runner.py summarize OUTPUT
```

For generated campaigns, pass `--cases .../generated/{tuning,holdout}/cases.jsonl`
to both `run` and `assess`. For immutable source snapshots, invoke that snapshot's
runner with `PYTHONPATH` set to its `src` directory; use the same virtual environment.
Final validation includes all pytest, Ruff, schema check, compileall, wheel isolation,
and the existing supported-OS CI when available. Local Linux results do not imply
that remote Windows/macOS CI has run.

Strategy screening is fixed before inspecting strategy outcomes: the 48 tuning
family instances plus 32 development cases selected by the ascending SHA-256 of
`20260907:screen:<id>`, seed 0, 16 jobs. The selection manifest is saved with the
screen corpus. Screen one strategy change at a time; a screen is not an adoption
claim. Run the complete 323 cases at grouped correctness stages and validate the
selected combination on all three final seeds and the untouched holdout families.

The tuning screen exposed an additional integration issue: a successful primary
NOMAD pass can stop with one answer before the scalar root-family search runs.
The subsequent scalar-branch experiment fixes its scan budget at two seconds,
uses every residual equation, and admits mathematically allowed zero-margin
endpoints. Its candidates undergo the existing refinement and final verification.
The scalar chart fallback also receives the ordinary precision-scaled scalar
iteration budget: adding a redundant equation must not replace that budget with
the 64-iteration multivariate chart cap. The original residual acceptance bound
and global deadline still apply.
This decision uses tuning outcomes only; the holdout remains unopened until the
final candidate is selected. Profile-led optimizations are also compared with
separate rank-first and adaptive-precision ablations on the same fixed screen.

`compare_solver_campaigns.py BEFORE AFTER REPORT` verifies matching input hashes,
references and execution/dependency contracts before applying numerical gates.
`summarize_solver_families.py CAMPAIGN FAMILY_MANIFEST REPORT.json` reports both
answer-set agreement between equivalent forms and correctness against the analytic
answer sets; two equally wrong outputs are not counted as a correct pair.
`merge_solver_campaigns.py TEMPLATE OUTPUT SEGMENTS...` preserves the earliest
committed run for each case/seed after an interrupted campaign, verifies identities,
and never treats a temporary worker file as a completed run.

The first complete 969-run candidate failed the adoption gate and remains in the
evidence directory. Answer stability at 250 digits was insufficient for later
500-digit domain-boundary and uncertainty checks, so that early-stop heuristic
was removed. Ordinary residual norms and squared scores retain their original
rounding; only overflow/subnormal cases use the safe fallback. A fixed investigation
of all newly regressed case identities, the gained case and the scalar partial-set
case uses all three seeds, followed by the unchanged 80-case screen. These are
development investigations, not substitutes for another complete 969-run campaign.
The held-out families remain unopened until a candidate passes the full gate.

The second complete candidate also failed: one previously correct run exhausted
its exactification deadline, with no compensating accuracy gain. The third
candidate preserves the ordinary finalization reserve but adds a three-second
minimum, capped at half the remaining interval and by the existing maximum.
This leaves refinement time on short intervals without changing verification
thresholds or the global deadline. It preserved all 18 investigation outcomes
and recovered the missing development-screen answer (31/32; tuning 48/48).
Selection remains conditional on a third complete campaign and the untouched
holdout; previous full-campaign failures remain part of the report.

The third complete candidate also failed (929 to 928 exact matches, total time
+0.51%), so the reserve floor was reverted. A profile-led polygon predicate
cache keys the full binary coordinates and active precision, never mutable
point identity or rounded coordinates. Float-contamination checks also avoid
context lookup for exact mpf/int operand types while retaining checks for
floats and subclasses. The predicate-cache-only investigation lost one of
27 original outcomes; the added operand fast path preserved all 17 baseline
correct outcomes in those 27 runs. These remain development investigations;
the fixed screen and another complete campaign decide selection. No holdout
outcome has been used to design these changes.

The fourth candidate passed the complete comparison: 929 to 930 exact matches
out of 969, total process time 27696.682 to 27435.932 seconds. Two case/seed
pairs improved and one regressed; all are retained in the comparison table.
Only then were the untouched holdout families run, once per source: 32 to 48
exact matches out of 48, total time 94.010 to 69.477 seconds, no extra answers.
No parameter adjustment followed the holdout. The observed development timing
improvement is small (0.94%); the report does not claim statistical certainty
or arbitrary-problem completeness.
