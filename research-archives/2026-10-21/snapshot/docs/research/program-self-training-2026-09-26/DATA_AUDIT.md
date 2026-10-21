# Numeric case data audit

Prepared 2026-09-26 for the program-self-training pilot. This audit covers the fixed numeric construction cases only; the prompts do not include proof text or a closed-form target relation.

## Frozen files and schema

- [`numeric_cases.py`](numeric_cases.py) is the deterministic CPU generator and validator.
- [`numeric_cases_public.jsonl`](numeric_cases_public.jsonl) contains 64 rows: four `visible` and four `repair` cases for each source configuration. These rows contain no construction coordinates.
- [`numeric_cases_private.jsonl`](numeric_cases_private.jsonl) contains all 448 rows, including the 64 public cases and the 384 `selection`/`final` cases. It carries coordinates and construction checks for audit; keep it private from the model.
- [`numeric_cases_rejections.private.jsonl`](numeric_cases_rejections.private.jsonl) records each rejected proposal, its sampled input points, deterministic split seed, and rejection reason.

The private-row contract is:

```json
{
  "case_id": "H01-visible-001",
  "source_id": "H01",
  "split": "visible",
  "givens": {"BC": 7.27106336176171, "AM": 5.169119294956025},
  "answer": 2.6121865084394753,
  "private_witness": {
    "points": {
      "A": [1.1255230834496195, 4.518810808864203], "B": [0.0, 0.0],
      "C": [7.27106336176171, 0.0], "M": [3.635531680880855, 0.0],
      "H": [1.12552308344962, 1.5307008272931482],
      "P": [2.3939423673061246, 2.235254180441302]
    },
    "shape_signature": {
      "kind": "sorted_normalized_triangle_sides",
      "normalized": [0.610492175, 0.95319941, 1.0]
    },
    "construction_checks": {"acute_scalene": true, "P_on_AM": true, "HP_perp_AM": true},
    "provenance": {"builder": "direct-coordinate-v1", "split_seed": 10610667775227195428, "candidate_attempt": 1}
  }
}
```

This is the frozen first private row. Its public projection omits `private_witness` and has exactly `case_id`, `source_id`, `split`, `givens`, and `answer`. The execution driver must use the split field to keep `selection` and `final` private and to reveal repair feedback only at the intended stage.

## Provenance and label construction

The eight sources are H01, H04, H07, H13, H14, H15, DA01, and DA05. Prompt wording and the allowed numeric-given names come from `docs/research/qwen35-diverse-sft-2026-09-24/english_templates.py` (`NUMERIC_EN`). Geometry primitives come from `benchmarks/humpty_configurations_v2/authoring/geo_primitives.py`; the relevant authored configuration records are `benchmarks/humpty_configurations_v2/authoring/h_revision.json` and `da_revision.json`. The configurations themselves are existing benchmark constructions, so this dataset tests numerical self-training on selected known constructions; it is not an unknown-problem discovery set.

For every proposal, the generator samples input coordinates and constructs the named points using the geometry primitives. It then obtains each given by a direct distance or cosine measurement and obtains the answer by measuring the requested distance or triangle area from the constructed points. It does not evaluate a target closed-form identity to create labels, choose branches, or accept/reject a case. For H07 the answer is measured from the constructed E, P, Q points; for H14 it is measured as the area of constructed A, H, R; other labels are likewise direct lengths. The stored coordinates allow the direct measurements and construction conditions to be independently recomputed.

After label construction, `numeric_cases.py --verify-only` rebuilds the eight original authoring witnesses from their source coordinates and checks agreement with the original authoring/canonical answers. All eight checks passed. These are sanity checks on a separate known witness, not the generator's label source.

## Split and construction checks

Each configuration has 56 accepted cases: 4 `visible`, 4 `repair`, 24 private `selection`, and 24 private `final`. The seed for each configuration/split is derived separately from root seed `20260926`, source ID, split name, and builder version. Each accepted case stores the split seed and proposal index.

Within each configuration, all 56 rows have distinct given tuples and distinct normalized shape signatures. Triangle signatures are sorted side-length ratios normalized by the longest side, so uniform scale changes do not count as new shapes. H07 uses the two tangent-circle radii normalized by AB. The comparison is within a source configuration; it is not a claim that constructions from different sources are mutually dissimilar.

The builder enforces the prompt's geometry and branch conditions: acute/scalene assumptions where specified; the indicated intersection on the stated side or forward ray; H04's T-B-C order; H07's M-before-N order; H13's K side and J interior to both segments; H14's nondegenerate circles and forward rays; H15's fixed 60-degree angle, finite intersections, and distinct lines; and DA05's M-D-E order. DA01 samples a broad angle range and only requires a nondegenerate scalene triangle, so obtuse cases are allowed. H15 enforces angle A = 60 degrees but does not impose an extra acute-triangle condition.

There were 506 rejected proposals before filling the requested splits: H04, 58 (`T_not_before_B`); H07, 398 (376 `M_not_closer_than_N`, 22 `not_acute_scalene`); H13, 50 (`K_not_opposite_A_side`). No proposal was discarded for a similarity duplicate or duplicate givens in this frozen run. The rejection ledger preserves the candidates and reasons.

## Precision correction and independent audit

An initial freeze rounded givens/answers to 12 significant digits and witness coordinates to 15. A separate independent comparison identified two H14 cases where this serialization lost enough precision to miss a `1e-8` absolute comparison: `H14-selection-016` and `H14-final-021`. The initial files and that audit are preserved in [`pre-precision-audit/`](pre-precision-audit/).

Before any model generation, serialization was changed uniformly to 17 significant digits for givens, answers, and witness coordinates. The same seed and generator produced the corrected manifests without changing accepted/rejected proposals. A row-by-row comparison confirmed that all 448 ordered case IDs, source IDs, split assignments, and stored normalized shape signatures are unchanged. The independent fresh audit then passed all 448 cases at absolute tolerance `1e-8` plus relative tolerance `1e-8`; it reported maximum relative error `6.47e-8` on a very small H14 area, within the combined tolerance. No sampling, filtering, geometry, or target-identity audit tolerance was changed.

## Frozen hashes

SHA-256 hashes of the frozen artifacts:

| File | SHA-256 |
|---|---|
| `numeric_cases.py` | `c6106b342dec5cac2a7742b1d469bbfecaa44db79023a80f83d62c95adf46f4c` |
| `numeric_cases_private.jsonl` | `f3e6bf82f8b2c342f95ed50f74bd9a5fc2c8a94fc8f1e11772f2ee53a6745445` |
| `numeric_cases_public.jsonl` | `31f75905dbdf1483fd8950e1c9ae5df851cccd59da574f08b41ccf0aba0cd854` |
| `numeric_cases_rejections.private.jsonl` | `991029621044106c06100ff3873c151ea38e6261eca79832df8dec82b34da821` |

Input-source hashes and a verification of the frozen files are recorded in [`numeric-provenance.json`](numeric-provenance.json). The precision-corrected manifests are frozen; regeneration or changes to sampling are outside this audit.
