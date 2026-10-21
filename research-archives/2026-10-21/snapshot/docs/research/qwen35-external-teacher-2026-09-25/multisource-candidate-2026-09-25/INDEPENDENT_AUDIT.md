# Independent audit: six-source numeric-variant candidate

**Scope:** CPU-only audit of the two candidate training datasets and all 18 added variant answers. No model outputs were opened, and no training or evaluation was run. The frozen dataset files were not changed.

## Findings

The 18 added answers are mathematically consistent with their stated givens. I independently checked the decisive derivations, exact final values, construction branches, and the proof text for all three variants from each of H01, H02, H07, DA02, DB02, and DB06. The base v0 teachers for these sources have accepted audits in the existing source audit file. I found no mathematical defect that blocks using these candidate files.

| Source | Independently checked relation and branch | Recomputed exact answers (v1, v2, v3) |
|---|---|---|
| H01 | `A·H=(BC/2)^2`; orthogonal projection onto `AM`; the acute-at-A condition puts `P` inside `MA`. | `48/13`, `40/11`, `69/13` |
| H02 | The normalized circle polynomial has center `Z(d)=(d,(AM²+(BC/2)²−2dx)/(2AK))`; each stated `U,V` is distinct from `A`, and the triangle is acute/scalene. | `2√34/5`, `2√109/5`, `3√146/11` |
| H07 | The common chord passes through `O`; the near intersection is `M=λN` with `λ=OA²/ON²`; the reflection and area derivation use the stated `0<λ<1` branch. Each variant has an acute scalene witness. | `36/7`, `9/2`, `16/5` |
| DA02 | The 120-degree angle conditions give `AT²=BT·CT`; the centroid vector lies on the circle `BTC` at parameter 3, yielding `TK=|AB−AC|`. Each new triangle is a positive scaling of the audited v0 triangle. | `5/2`, `4/3`, `1` |
| DB02 | The two similarity relations give the stated interior `P,Q`; the coordinate intersection parameter is `36/49` in every positive scaling. | `9`, `18`, `4` |
| DB06 | The side-product equality forces both diagonal points to be their midpoints; the vector identity then gives `4XY²=AB²+BC²+CD²+DA²−AC²−BD²`. Each is a positive scaling of the audited convex cyclic v0 construction. | `125/192`, `5/48`, `20/27` |

For H02, I specifically checked all three acute/scalene and intersection branches. The listed coordinate witnesses have `0<x<BC/2`, positive altitude, positive angle-A dot product, and pairwise distinct side squares. Both `D_i` lie strictly inside `BC`; the computed `s_U,s_V` values are nonzero, so the defining circles and `A,U,V` are nondegenerate.

For H07, the tangent-point assignment is stated explicitly in each added problem. The given `ON` values produce `λ=37/49`, `13/16`, and `17/25`; these are all strictly between zero and one. The acute scalene witnesses and the stated areas check out.

## Dataset and exposure checks

- Both arms contain 50 rows: the exact same 32 frozen base rows plus 18 additions. Both have 32 distinct source IDs; each of the same six selected sources has four rows. The five held-out source IDs H03, H04, H08, H14, and H15 are absent from both arms.
- The 18 repeat-control additions exactly copy their source v0 prompt and answer. The 18 numeric additions use v1–v3 givens and final values from the benchmark training variants; I checked those values against each English problem statement and teacher answer.
- All candidate prompts and answers are English; no CJK characters occur. The longest prompt-plus-answer sequence is 1,238 tokens, below the 8,192-token cap.
- I reproduced the per-row counts with the local Qwen3.5 tokenizer and the training driver's chat-template path. Numeric arm: 13,014 prompt tokens, 29,973 assistant tokens including EOS, 42,987 total. Repeat arm: 12,896 prompt tokens, 30,520 assistant tokens including EOS, 43,416 total. The numeric arm therefore has 1.79% fewer assistant tokens and 0.99% fewer total sequence tokens. The row counts and optimizer updates can match, but token exposure is not exactly matched.
- The dataset and audit hashes in `hashes.json` match the files on disk.

## Design caveats

1. **H07 wording differs between arms.** The three numeric variants explicitly say the first circle is tangent at A and the second at B. The repeat-control rows retain the common v0 wording, “Two circles tangent to line AB at A and B”. That original wording naturally implies the intended correspondence, so I did not find a geometry error; however, the added treatment rows also clarify the mapping. This is a small prompt-content confound in a comparison intended to isolate numeric variation from exact repetition.
2. **Token exposure differs slightly.** The repeat arm has 547 more assistant target tokens including EOS (1.79%). This is modest and does not invalidate a small diagnostic, but it should be recorded when interpreting a difference between arms.
3. **The variant mechanism is narrow.** These additions mostly change numerical instances while reusing the same proof structures; DA02, DB02, and DB06 are positive scalings of their audited source constructions. A result would diagnose numeric-instance exposure versus repetition, not establish that varied proof styles or broader theorem diversity cause transfer.

**Disposition:** Suitable as a CPU-audited candidate for the stated narrow diagnostic, with the H07 wording difference and small token imbalance recorded before any run.
