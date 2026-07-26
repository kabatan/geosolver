# v15 candidate tournament — 2026-07-22

## Decision

The best solver under the frozen development-145 run remains
`champion_v2_poc_preloaded`.

| arm | exact-set score | extra/wrong | run wall | case median | case p95 |
|---|---:|---:|---:|---:|---:|
| `champion_v2_poc_preloaded` | **131/145** | 0 | 2805.44 s | 138.07 s | 177.042 s |
| `champion_v2_poc_archive_levy_tail` | 130/145 | 0 | 2681.06 s | 135.06 s | 177.044 s |

Both full runs used the same selected dataset digest
`b912d3fcd0a40e1de11d4c793c565a51d4eb5f33651ca4931eb30fcef6e4fced`,
180 s total / 146 s search, 256 starts, 600 callbacks per start,
aggregate cap 153600, seed 0, seven fresh pinned processes on CPUs
`0,1,2,3,5,6,7`, and native thread limits of one. Truth was isolated from
the solver and read only by the frozen offline exact-descriptor-set scorer.

Archive Levy was about 4.4% faster in this pair, but exact-set score has
selection priority. Its development gains were `OMC101(F)` and `OMC171(B)`;
its losses were `OMCE005(F)`, `OMC037(D)`, and `OMC077(D)`. Thus the D1
screen signal did not survive D2: gain/loss was `+2/-3`, net `-1`.

## Current champion components

The selected arm contains the mature direct Broyden/TR/LM search,
retained-invalid corrective starts, strict near-root restarts, the target-free
endpoint reservoir, leftover-only restoration, adaptive H1 HP portfolio
(512/768 thin and event-Broyden, without fresh 1280), the zero-variable exact
AST route, PointOnCircle periodic semantic parity, strict triangle guard
semantics through the active HP evaluator, and the common charged precision
runtime preload.

## Re-screened candidates

All screen runs used the same frozen runner and offline exact-set scorer.

| candidate | screen result | decision |
|---|---|---|
| bounded/periodic Wave 1 | 5 s: 17/24 vs 17/24; 20 s: 15/24 vs 15/24 | no current gain |
| guard-stratum novelty | 16/24 vs 17/24; gain/loss 0/1 | STOP |
| direct-exact-first | 13/24 vs 17/24; gain/loss 0/4 | STOP |
| callback-ledger v4 | search-only terminal; no end-to-end exact output | HOLD, not a finalist |
| per-core HP scheduler binding | failed the second existing execution contract after the one allowed mechanical repair | HOLD |
| archive Levy tail | three-seed aggregate 50/72 vs 48/72; gain/loss 2/0 | advanced to development 145 |
| Levy + bounded | 15/24 vs Levy 16/24; lost `OMCB032(C)` | STOP |
| Levy + branch-diverse | 16/24 vs Levy 16/24, identical case set | remove non-contributor |

Archive Levy was therefore the only newly connected independent candidate to
pass the multi-seed screen. Its full-145 result is the basis for rejection,
not the earlier generated or short-screen result.

## HOLD audit

The audit covered all 476 candidate directories. HOLD was not treated as an
algorithmic failure by default.

Promising but not thinly connectable to the current closure, and therefore
still HOLD under the no-infrastructure rule:

- triggered mixed-precision refinement: the available seam replaces the
  current strict near-root kernel;
- adaptive exact-coordinate tail: its preserve-binding arm excludes the
  active PointOnCircle HP bridge;
- guard/equation swap: its frozen 24x128/3072 search and output contract do
  not match the current 256x600/153600 contract;
- exact-SVD same-model retry: the mature local kernel has no step-injection
  seam;
- per-core HP scheduling and callback checkpointing: isolated evidence exists,
  but no existing current full-terminal seam passed the one-repair rule;
- complex-gamma homotopy, nonlinear Schwarz/FAS, and topological/certified
  low-degree approaches: generated or local evidence exists, but a source-only
  real seam or multi-cluster applicability is missing.

These were not assigned artificial zero scores. They were excluded from the
current executable tournament because connecting them would require precisely
the runner/compiler/kernel work that the experiment's 10% infrastructure cap
forbids.

Empirical STOP lineages include the secant variants, nonlinear
Krylov/Anderson, Newton-MR and additional Broyden variants, compensated normal
equations v2, geodesic LM, random subspace, MLSL, DIRECT, DYCORS/RBF, periodic
local metric, topology composition, rootlike HP, and stateful halving. Their
stored real or cross-family results show no gain, a loss, or unacceptable work
regression; renaming or retuning the same mechanism is not a new candidate.

Results from the modular exact source-link v1 leakage lineage, the pre-freeze
roundoff cross-validation lineage, and other protocol-tainted artifacts were
not used for selection or score claims.

## Artifacts

- incumbent full result:
  `results/repro-20260722-champion-v2-poc-preloaded-development145-180s-jobs7-v1/`
- Levy full result:
  `results/tournament-20260722-archive-levy-development145-180s-seed0-jobs7-v1/`
- Levy three-seed screens:
  `results/tournament-20260722-archive-levy-screen24-30s-search20-seed{0,1,2}-jobs1-v1/`
- hybrid ablations:
  `results/tournament-20260722-levy-{bounded,branch}-screen24-30s-search20-seed0-jobs1-v1/`

The jobs=7 full comparison is the frozen formal tournament used here. The
legacy global HP lock makes paired per-case timing noisy; notably, Levy lost
`OMC037(D)` even though its postlude did not activate on that case. Therefore
the small speed difference is supplementary, and the result does not prove
that Levy is universally worse under every serial schedule. It does establish
that Levy fails the required loss-zero promotion gate and does not beat the
incumbent in the agreed formal run.
