# Blind grading: H03 fresh4 answers

Grading was performed on `answer_text` only using the frozen stage-localization rubric. No mapping vault, arm directory, or prior grade was opened. H03 requires the construction-to-H-foot-on-median mapping, the diameter-HG circle and its center, the midpoint relation for Z and its OZ application. `T015` has no answer text and is left unscored.

| Blind ID | Mapping claim / proof | Downstream relation / proof | Exact value | Complete proof |
|---|---|---|---|---|
| T003 | fail / fail | fail / fail | fail (7; expected 28/3) | fail |
| T004 | fail / fail | fail / fail | fail (13/2 (6.5); expected 26/3) | fail |
| T006 | fail / fail | fail / fail | fail (7; expected 26/3) | fail |
| T012 | fail / fail | fail / fail | fail (13; expected 26/3) | fail |
| T015 | not scored: blank, length-stopped | not scored: blank, length-stopped | not scored: blank, length-stopped | not scored: blank, length-stopped |
| T017 | fail / fail | fail / fail | fail (7; expected 28/3) | fail |
| T021 | fail / fail | fail / fail | fail (13; expected 26/3) | fail |
| T024 | fail / fail | pass / fail | pass (28/3; expected 28/3) | fail |

## Evidence and errors

- **T003** — Does not identify Pa as the foot from H to AMa. Instead asserts an unsupported relation involving MaPa and the foot from A to BC, then uses an invalid isosceles-limit/continuity argument to identify Z with the nine-point center. The proposed OZ=OH/2 gives 7, not 28/3.
- **T004** — Mentions the projection of H onto BC but never connects the constructed Pa to the foot from H onto AMa. The vector/algebra derivation repeatedly stops or labels its own guesses incorrect, then asserts the nine-point-center result without proving it. The final half-OH relation is wrong for this construction.
- **T006** — Does not establish the H-to-median-foot mapping. It speculates about several unrelated loci and ultimately states Pa,Pb,Pc lie on the nine-point circle as an unproved “known” lemma. This gives the incorrect half-OH relation and 7.
- **T012** — No H-to-median-foot mapping. The central construction claim is false: it says KaLa has midpoint Ma, so (AKaLa) is centered at Ma and Pa is the reflection of A across Ma. In general the midpoint of KaLa is not Ma. The subsequent valid-looking vector calculation depends on that false premise and concludes Z=H; exact value 13 is wrong.
- **T015** — answer_text is blank and finish_reason is length. No final answer was available; no mathematical score assigned.
- **T017** — Does not establish the H-to-median-foot mapping. It explicitly notices that Ma generally is not the midpoint of KaLa, and its coordinate work does not derive the claimed nine-point result. It then substitutes pattern-matching/unsupported “known lemma” assertions for proof; OZ=OH/2 and 7 are wrong.
- **T021** — Identifies Pa with an inversion of A in a circle centered at Ma, not the foot from H to AMa. The key assertion that the circumcenter of those inversion points is H is unsupported and false; the answer gives Z=H and OZ=13.
- **T024** — States the correct target relation Z is the midpoint of HG, hence OZ=2/3 OH, and gives 28/3. It does not identify Pa as the projection of H onto AMa or prove the center relation from the construction. The purported bridge is asserted as a “remarkable property”; its worked right-isosceles example is outside the acute-scalene setup and contains unresolved/incorrect point calculations. Thus the relation and exact value are right, but not proved.

The per-entry machine-readable record is in `grades-H03.json`.
