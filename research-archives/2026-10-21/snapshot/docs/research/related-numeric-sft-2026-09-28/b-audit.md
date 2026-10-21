# PN06–PN10 numerical generator audit

`generate_b.py` samples the original triangle for each problem, constructs every named point by the specified line and circle operations, and measures the requested target from those points. The answer key identities are checked only after target measurement. The code never uses them to produce a target.

Run: `.venv/bin/python docs/research/related-numeric-sft-2026-09-28/generate_b.py --per-type 12 --output docs/research/related-numeric-sft-2026-09-28/b-cases.jsonl`

Seed: `20260928`. Output: 60 JSONL records, 12 per type, 60 unique prompts and 60 distinct normalized triangle shapes. Within each type, the smallest pairwise Euclidean distance between the two side-ratio signatures is above `0.018`.

| Pack/source | Count | Minimum shape distance | Largest relative audit residual |
| --- | ---: | ---: | ---: |
| PN06 / DA07 | 12 | 0.0203155 | 2.85e-14 |
| PN07 / DA08 | 12 | 0.0398702 | 7.23e-14 |
| PN08 / DA11 | 12 | 0.0362413 | 1.43e-14 |
| PN09 / DB02 | 12 | 0.0371703 | 4.27e-14 |
| PN10 / DB12 | 12 | 0.0187021 | 5.69e-14 |

The numerical audits check the source angle, midpoint, tangency, parallelism, circle-membership, intersection, branch, and given conditions relevant to each construction. PN06 specifically checks the order A,M,X. PN09 computes the two rays by the original angle conditions and verifies both P and Q lie strictly inside BC. PN10 keeps angle A at 45 degrees, varies the adjacent side ratio, and checks X lies inside ABC; it does not impose an acute-triangle condition. Source-solution identities are kept in audit fields solely as independent checks.

The public `problem_en` field contains the measured givens formatted with 17 significant digits. Geometry points and audit residuals are authoring metadata; they should not be placed in a learner prompt.
