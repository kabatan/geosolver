# Adjudication: H04 blind T014

## Question

T014 received `complete_proof=true` in the H04 blind grade. The independent base-only grade marked it incomplete because the answer says “Since the triangle is scalene, `MA ≠ MB`,” which is not a valid implication in general. This note adjudicates that item without changing either frozen grading file.

## Finding

The false implication is not explicitly retracted. However, it is immaterial to the proof for the stated problem, and the complete proof should pass.

The cancellation in T014 requires `MA² − MB² ≠ 0`. The prompt supplies that `∠A` is acute. With `a = BC`, `b = CA`, and `c = AB`, Apollonius' theorem and the cosine rule give

\[
MA^2-MB^2
=\frac{2b^2+2c^2-a^2}{4}-\frac{a^2}{4}
=\frac{b^2+c^2-a^2}{2}
=bc\cos A>0.
\]

Thus the factor canceled in T014 is nonzero for every triangle in the prompt, independently of whether the triangle is scalene. The answer also states that `MA = MB` would make `P = A` and the perpendicular-bisector construction degenerate; this is consistent with the same exclusion, though it does not retract the incorrect “scalene implies” rationale.

## Proof assessment

The rest of T014 supplies a valid route: it derives `MA · MH = MB²` in coordinates, projects `H` to `P`, uses `TA = TP` to obtain `AT² = MT² − MB²`, applies the specified exterior order `T-B-C` to select `MT = MB + BT`, and substitutes `BT = 5/4, BC = 14` to get `AT = √305/4`.

The erroneous scalene rationale is a local justification error whose needed fact follows directly from the acute-angle premise. It does not invalidate the selected route or introduce a contradictory conclusion. Therefore, under the frozen rubric's requirement of a self-contained relation, branch selection, and exact application, **T014 passes complete proof**. The inaccurate general condition should remain noted as an error, but it does not change the complete-proof score for this instance.

## Scope

This is a separate post-unblinding adjudication only. The frozen H04 blind grade and base-only grade files were not edited.
