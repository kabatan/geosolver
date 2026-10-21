# Evaluation comparability audit

Old 12-source result decomposes into common eight sources **6→9/16** and removed four sources **5→7/8**. This is a posthoc subset of saved responses, not a newly randomized causal experiment.

| Source | Old base/2 | Old numeric128/2 | New base/2 | New correct128/2 | New correct512/2 | New shuffle512/2 |
|---|---:|---:|---:|---:|---:|---:|
| DA03 | 2 | 2 | — | — | — | — |
| DA06 | 1 | 2 | — | — | — | — |
| DA07 | 2 | 2 | — | — | — | — |
| DA11 | 0 | 1 | — | — | — | — |
| DA15 | 1 | 2 | 1 | 1 | 2 | 2 |
| DB01 | 2 | 2 | 1 | 2 | 2 | 2 |
| DB08 | 0 | 2 | 2 | 1 | 2 | 2 |
| DB16 | 1 | 1 | 0 | 0 | 0 | 0 |
| H02 | 0 | 1 | 1 | 0 | 0 | 0 |
| H03 | 0 | 0 | 0 | 0 | 1 | 0 |
| H08 | 0 | 0 | 1 | 2 | 1 | 2 |
| H12 | 2 | 1 | 1 | 2 | 0 | 1 |

All 16 common job IDs have byte-identical problem text and identical model prompt-token IDs; hence stated numerical givens are identical. All 16 inference seeds differ. The 32k model revision, sampling parameters, batch size, cap and context match; driver hashes differ (`f94829afb059f9514fd563b6cfcb849665d84fee09bc0e00ef6baea77f88c583` vs `007c1cd7830d4b7ba288227414ae1897a9eb66843f243136a7521decc3a5e7b4`), but the source diff only adds the 131k cap/context pair to the allowed bounds. Batch-start positions differ for 10/16 jobs because the batch job lists changed. Final caps differ in 3/16 base jobs and 3/16 128-update jobs. The JSON contains per-job seed, prompt/hash, token-hash, batch and cap comparisons and empty prompt diffs.

The old 128-update numeric adapter was trained on 56 examples in seven constructions; the new correct128 adapter was trained on 80 examples in ten constructions. Their adapter hashes differ (`aca6d2f78e713b8979322728a397839536067a4bd827ee71b8e7b3f4a77e19da` vs `34b65d72b03f1e0ca04bd302b9a5194f347991b843d9abe2497bbddf513efd06`). Thus only the base condition reuses the same checkpoint across studies; the two 128-update SFT results also differ in training data. Their cross-run answer flips cannot be assigned solely to inference changes.

## Saved-budget outcomes

| Evaluation/arm | 32k common | 81k-with-carry common | 131k-with-carry common |
|---|---:|---:|---:|
| Old base | 7/16 (stop 15) | 6/16 (stop 16) | — |
| Old numeric128 | 7/16 (stop 13) | 9/16 (stop 15) | — |
| New base | 7/16 (stop 15) | 6/16 (stop 15) | 7/16 (stop 16) |
| New correct128 | 6/16 (stop 14) | 8/16 (stop 16) | 8/16 (stop 16) |
| New correct512 | 8/16 (stop 15) | 9/16 (stop 16) | 8/16 (stop 16) |
| New shuffled512 | 8/16 (stop 15) | 9/16 (stop 16) | 9/16 (stop 16) |

The 81k/131k columns carry forward non-regenerated jobs. The response at a larger cap is a fresh sample, not a continuation of the 32k prefix; exact token-prefix checks for every regenerated new response are recorded in the JSON, alongside the old saved prefix ledger. All saved stage-specific outcome changes and final cross-run job flips are enumerated in the JSON. Consequently, observed one- or two-answer differences across runs can be consistent with changed inference seeds, batch composition and selective regeneration; this audit cannot apportion their effects or infer what would have happened under identical seeds.

The old 11→16/24 gain includes **3** net answers in the retained sources and **2** in the four omitted sources. The new 16-job score and old restricted score therefore differ in both evaluation composition and stochastic realizations. A matched-seed, matched-job-list replication is needed to attribute a transfer difference to training.

Reproduce: `.venv/bin/python /home/kabatan/work/solver/docs/research/numeric-sft-success-failure-analysis-2026-09-28/compare_evaluations.py`. This script reads saved jobs, receipts, responses and score ledgers only; it does not generate or train a model.
