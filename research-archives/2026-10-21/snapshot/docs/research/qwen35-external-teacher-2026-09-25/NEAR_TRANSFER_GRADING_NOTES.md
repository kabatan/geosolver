# Independent geometry checks for blinded grading

These notes were prepared from frozen problem statements and `heldout-near-transfer/answer_key.json` before opening any fresh model answer. They supplement `heldout-near-transfer/GRADE_RUBRIC.md`; an equivalent valid proof need not use the exact coordinates below. Do not show the notes or key to a model during evaluation.

| ID | Exact answer | Decisive proof requirement |
|---|---|---|
| H03 | `14/3` | Establish that each angle-bisector-circle/median second intersection is the orthocenter's projection onto that median; then derive that the three projections lie on a circle centered at `O + (2/3)(H-O)`. Merely naming the center fails proof. |
| H04 | `sqrt(69)/2` | Derive the orthocenter projection onto `AM`, combine it with `TA=TP`, remove the impossible factor using acuteness, and reach `AT²=MT²-(BC/2)²` on the `T,B,C` branch. |
| H08 | `85/13` | Use both tangent-circle equations and `AP=AC` to derive the angle relation (or an equivalent cross/dot-product identity); verify the acute-angle branch, then obtain the area. Naming a tangent theorem without its decisive equality fails proof. |
| H14 | `1805/2928` | Show by `M`-centered inversion that `D,E` lie on the inverted circle and the two circles through `M` map to `AB,AC`, so `R` is the inversion of `A`; derive that this equals the orthocenter projection onto `AM`, then compute the area. |
| H15 | `64*sqrt(97)/97` | Establish the A-symmedian from the two tangents, use the three reflections to derive `K=midpoint(AD)`, and apply Apollonius. A naked three-reflection midpoint claim fails proof. |
| H01 | `25/13` | With `M=0`, half-base `m`, and `A=(x,y)`, derive `H=(x,(m²-x²)/y)`, `A·H=m²`, hence `MP=m²/AM` and `AP=AM-m²/AM`; verify the acute branch. |
| H02 | `4*sqrt(178)/13` | Derive both second-intersection parameters on `AC,AB` for circles `ABD,ACD`, then the two center equations to show the center moves affinely with `BD` at speed `AM/AK`; establish the sign from `BK>KC`. |
| H07 | `20/3` | Derive the two-circle radical axis through `O`, the same-ray product `OM·ON=(AB/2)²`, and the reflection/line-intersection geometry leading to `PQ=AB(1-OM/ON)` and height `2MF`; use the closer-point branch. |
| H13 | `1053/79` | Derive the circle tangent and sign branch for `K`, compute `J`, and verify that a candidate center on `AC` is equidistant from `B,J,K`; saying only that the center is on `AC` is insufficient. |

Apply the four independent binary fields from the rubric. A correct final number obtained from an invalid relation can pass only exact-value, not useful relation, proof, or correct use. An answer may use a different valid argument. Flag borderline cases for a second review rather than inferring unstated steps.
