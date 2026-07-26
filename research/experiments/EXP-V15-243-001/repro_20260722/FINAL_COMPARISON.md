# development145 fixed-run comparison (2026-07-22)

## Fixed protocol

- Frozen development subset: 145 cases, SHA-256 `b912d3fcd0a40e1de11d4c793c565a51d4eb5f33651ca4931eb30fcef6e4fced`
- Dataset SHA-256: `e587c6ea3f315f270e13cae859bba947f52e59afb651b7485061fdc49be06b8f`
- Fresh process per case; seven pinned physical cores: `0,1,2,3,5,6,7`
- Native thread count one; seed 0
- Total/search budgets: 180/146 seconds
- 256 starts, 600 callbacks/start, aggregate callback cap 153600
- The solver never receives truth or known target count.
- After every solver process exits, the fixed scorer compares the returned exact descriptor set with frozen truth. A case passes only on complete set equality.
- Precision-runtime preload is charged to the case budget and is common to all measured arms. It removes only the cold-import artifact from the old one-second baseline selection window.

## Results

| arm | exact-set | missing | extra | accepted | worker median | worker p95 | full-run wall |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_preloaded | 123/145 | 22 | 0 | 145/145 | 96.96 s | 163.69 s | 2153.54 s |
| champion_v1_preloaded | 127/145 | 18 | 0 | 145/145 | 148.01 s | 177.04 s | 2890.65 s |
| champion_v2_preloaded | 127/145 | 18 | 0 | 145/145 | 147.07 s | 177.05 s | 2848.33 s |
| **champion_v2_poc_preloaded** | **131/145** | **14** | **0** | **145/145** | **138.07 s** | **177.04 s** | **2805.44 s** |

`champion_v2_poc_preloaded` also has worker mean 129.86 s, worker max 177.09 s, outer median 139.48 s, and outer p95 178.25 s. There were no process timeouts or crashes.

## Paired result for the selected arm

Versus `champion_v1_preloaded`, the selected arm gained four cases and lost none:

- gains: `OMCE004(C)`, `OMC009(C)`, `OMCB032(C)`, `OMCB036(F)`
- losses: none

Versus `champion_v2_preloaded`, it gained four cases and lost none:

- gains: `OMCE005(F)`, `OMCB032(C)`, `OMCB036(F)`, `OMC125(F)`
- losses: none

The remaining failures are:

`OMCE002(E)`, `OMCE011(E)`, `OMCE010(E)`, `OMC021(D)`, `OMC035(D)`, `OMC048(F)`, `OMC060(C)`, `OMC135(E)`, `OMC171(B)`, `OMC168(E)`, `OMCB010(B)`, `OMC084(E)`, `OMC101(F)`, `OMC118(F)`.

## Selection

The current best measured solver is `champion_v2_poc_preloaded`: champion_v2's zero-variable exact route plus the existing source-general PointOnCircle periodic-semantics repair, with the common precision-runtime preload. Its fixed development145 performance is **131/145 (90.34%)**, with extra/duplicate/timeout/crash all zero.

The branch-diverse reservoir was not promoted to another full run because its saved paired screen was an exact tie (`16/24` versus `16/24`, extra zero). The direct-exact timing composition was stopped after the first existing-seam connection failed; no runner adapter or repair chain was added.

## Evidence

- `../results/repro-20260722-baseline-preloaded-development145-180s-jobs7-v1/`
- `../results/repro-20260722-champion-v1-preloaded-development145-180s-jobs7-v1/`
- `../results/repro-20260722-champion-v2-preloaded-development145-180s-jobs7-v1/`
- `../results/repro-20260722-champion-v2-poc-preloaded-development145-180s-jobs7-v1/`

Selected-arm SHA-256:

- `RESULT.json`: `1c7593cbf64161afa84929bfda61759e3c38149256aecd18be38f54129f86607`
- `OFFLINE_SCORE.json`: `8a62d61cc0a3f7a9ea43fb15006a743b1e5ad108040f4050cf529d05ec13db12`
