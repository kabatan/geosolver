# Anonymous numeric derivation review: initial C

I read all five answers in full and applied the calibrated numerical criterion in `REVIEW_RUBRIC.md`. An exact, applicable known construction result can support a numerical answer without a theorem name or local proof. I checked only the properties actually invoked against `numeric-review-reference-compact.json`; the reference did not fill missing steps.

| Case | Derivation | Geometric core | Numerical error | Reason |
| --- | --- | --- | --- | --- |
| numeric-01 | **valid** | yes | no | Explicit known lemma `PQ ⟂ AC` for the stated configuration (lines 76–77, 133); distances give `MV=1`, `QV=10`, `PQ=15/2` (134–135). |
| numeric-02 | **invalid** | no | no | External-tangent formula is right (330), but `JU=5` comes from inadmissible isosceles specialization and assumed invariance (408–409, 495), not a demonstrated or invoked exact result. |
| numeric-05 | **valid** | yes | no | Explicit known tangency of `PX` to circle `KLX` (101–102, 196); `PZ=12` and power `36` give `PX=6` (200–203). |
| numeric-06 | **valid** | yes | no | States the exact angle-condition tangency lemma (107–109) and retains it in the final derivation (178–183), yielding `PX=6`. |
| numeric-11 | **valid** | yes | no | Explicit known diameter-`AO` lemma (363), retained as right angle at `F` (390); Pythagoras gives `OF=5` (365–366). |

Cases 01, 05, 06 and 11 have a presentation boundary: they explore guesses or say “assume” while omitting a local proof of the specialized result. A strict proof rubric could reject them. Under this numerical rubric, each answer explicitly adopts the precise true construction property and carries out the relevant arithmetic. The numerical-neatness remarks do not replace those retained cores.

For case 02, a generous reading could interpret the correct `JU=5` as an implicit theorem application. Its actual final reasoning instead assumes a forbidden isosceles case, assumes invariance, and chooses a center distance by plausibility. The exact external-tangency theorem is true, but is not supplied by this answer.

The JSON companion records line-checked quotations, alternative boundary readings, and per-file read coverage. No private condition mapping or model information was read.
