# EXP-DEF-001 result index

The corrected, provenance-bound v2 development run completed successfully, but
neither `D1-DGN-MIXED` nor `D2-DGN-FAIR-RETRY` passed the frozen safety,
mechanistic-recall, cross-family-repeat, or preparation gates. Neither candidate
qualified for the one allowed retune. The mechanical decision is therefore
`bounded-negative-stop-before-locked` with no selected variant.

This is an ideal-analytic-Jacobian mechanism result only. It rejects this frozen
v2 policy under its registered gate; it does not establish that every possible
deflation method is ineffective. Locked inputs were neither generated nor
opened, and no product dependency or public policy was changed.

The runner did not open Gold. The independent analyzer first verified the v4
source freeze, clean Git blobs, preflight, exclusive-run audit, execution
identity, row ordinals, frozen starts, and all raw hashes. It then opened Gold
and reconstructed 33,976 action rows into 5,760 metric rows.

Raw evidence is stored as 96 deterministic gzip members under
`development-v2/raw/`. `raw-archive-manifest.json` binds every member to its
original uncompressed SHA-256. The analyzer was replayed after compression and
all analysis hashes remained byte-identical.

Key artifacts:

- `summary.json`: concise decision, provenance, safety counts, and artifact hashes.
- `development-v2/analysis/summary.json`: complete machine-readable analysis.
- `development-v2/analysis/decision.md`: human-readable frozen decision.
- `development-v2/analysis/aggregate.csv`: prefix metrics.
- `development-v2/analysis/assessed-rows.jsonl.gz`: Gold assessments by action row.
- `development-v2/raw-archive-manifest.json`: deterministic archive binding.

The zero-required safety counters are row-level canonical endpoint assessments
across the full formal trace, not counts of public answers. In particular,
`false_accepted` means a canonically accepted endpoint outside independent Gold,
and `positive_residual_promotion` is the registered accepted-no-root counter.
