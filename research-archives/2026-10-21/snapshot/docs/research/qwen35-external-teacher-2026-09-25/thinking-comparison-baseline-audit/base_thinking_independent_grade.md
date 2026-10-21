# Independent blind grade: base Thinking, 81,920-token cap

Graded the six base-weight fresh4 outputs using `STAGE_LOCALIZATION_GRADING.md`. Every answer ended naturally (`stop`) and included one `</think>`; token counts below include generated thinking and answer tokens. Four of six exact numeric applications are correct, but none has a complete proof under the frozen rubric. The exact-value count is separate from proof validity: H03 fresh4-1 and both H14 values are numerically correct conditional on relations the answers do not establish. These six numeric probes repeat three construction families; they are not six independent families.

| Probe | Tokens / finish | Mapping claim / proof | Downstream relation / proof | Exact value | Complete proof |
|---|---:|---|---|---|---|
| H03 fresh4-0, OH=13 | 59,877 / stop | absent / no | wrong center relation / no | 13; expected 26/3 — fail | no |
| H03 fresh4-1, OH=14 | 62,861 / stop | absent / no | correct midpoint-HG claim / unsupported | 28/3 — pass | no |
| H04 fresh4-0, BT=14/11, BC=13 | 22,513 / stop | given / supplied | correct relation and branch proof | model simplifies radical incorrectly; expected √2198/11 — fail | no |
| H04 fresh4-1, BT=5/4, BC=14 | 29,469 / stop | given / supplied | correct relation; near-complete proof, but invalid stated reason for cancelling a factor | √305/4 — pass | no, conservative |
| H14 fresh4-0, AH=13/4, AR=39/20 | 35,393 / stop | absent / no | right angle asserted, not derived from construction | 507/200 conditional on relation — pass | no |
| H14 fresh4-1, AH=17/3, AR=34√13/39 | 36,366 / stop | absent / no | right angle asserted, not derived from construction | 289/39 conditional on relation — pass | no |

The H03-0 proof substitutes the false claim Z=H. H03-1 gives the correct target ratio and numeric answer, but never proves the center relation; its attempted special-case check is internally inconsistent and is not a proof for acute scalene triangles. Both H03 answers recognize the inversion/power construction but do not state or derive that the constructed points are the orthocenter projections.

H04-0 establishes the projection formula, perpendicular-bisector condition, exterior branch, and product relation, but makes a radical simplification error in the final value. H04-1 derives the equivalent relation and gets the value right. It says scalene implies MA≠MB, which is false. It also notes that MA=MB would make P=A and the construction would break down; because T is defined through a perpendicular bisector of AP, that fact could justify cancellation. But the answer does not clearly retract its false scalene implication. Under the frozen rubric's conservative treatment of unresolved contradictions, I do not count it as a complete proof.

Both H14 answers get the numerical area right conditional on a right angle at R, but do not show the required construction-to-projection mapping R∈AM. They assert the circle-with-diameter-AH relation and refer to unspecified analytic calculations; one additionally treats the chosen numbers as evidence for the intended geometry.

Per-item evidence and statuses are in [base_thinking_independent_grade.json](base_thinking_independent_grade.json).
