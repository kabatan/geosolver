# Independent audit of H04 complete-proof grades

This is a post-freeze audit of T007, T013, T014, and T019, using their blind-packet `answer_text` and the frozen H04 rubric. The frozen grade files were left unchanged.

## Shared mathematical check

Set `M=(0,0)`, `B=(-c,0)`, `C=(c,0)`, `A=(u,v)`, `S=u^2+v^2=AM^2`, and `c=MB=BC/2`. Then

\[
H=\left(u,\frac{c^2-u^2}{v}\right),\qquad
\overrightarrow{MA}\cdot\overrightarrow{MH}=c^2.
\]

So the projection of `H` onto `AM` is `P=(c^2/S)A`. Equating `TA^2=TP^2` for `T=(t,0)` gives

\[
(S-c^2)\bigl(S+c^2-2tu\bigr)=0.
\]

The canceled factor is nonzero for the stated acute triangle: `S-c^2=AB·AC cos(A)>0`. Hence `2tu=S+c^2`, and then `AT^2=t^2-c^2`. The order `T-B-C` fixes the branch `t=-(c+BT)`, giving

\[
AT^2=(c+BT)^2-c^2=BT(BC+BT)=BT\cdot TC.
\]

## Item findings

| Blind ID | Audit finding |
|---|---|
| T007 | **Complete proof upheld.** Its final coordinate solution correctly derives the foot, the perpendicular-bisector intersection, and `AT^2=t^2-c^2`. It then uses `T-B-C` to choose `t=-(c+BT)`. Earlier incorrect reflection and sign guesses are explicitly revisited and corrected. Final value `sqrt(2198)/11` is correct. |
| T013 | **Complete proof upheld.** Its projection and equal-distance algebra yield `2tu=S+c^2`, `AT^2=t^2-c^2`, then `AT^2=BT·TC`. The sentence “`k!=1` … generally” is terse, but the given acuteness supplies the needed nonzero factor `S-c^2=AB·AC cos(A)>0`. The exterior order is used to take the correct product branch. Final value `sqrt(2198)/11` is correct. |
| T014 | **Core derivation and value upheld; strict no-unretracted-false-claims criterion needs a flag.** The answer correctly proves `vector(MA)·vector(MH)=MB^2`, obtains `vector(MP)=(MB^2/MA^2)vector(MA)`, applies `TA=TP`, cancels `MA^2-MB^2`, and uses `T-B-C` to get `MT=MB+BT`. Its cancellation is valid: if `MA=MB`, its own projection formula gives `P=A`, so `AP` has zero length and no unique perpendicular-bisector line; the stated construction of `T` would not be defined. Independently, acuteness gives `MA^2-MB^2=AB·AC cos(A)>0`. However, it also says “scalene implies `MA!=MB`” and equates `MA=MB` with isosceles cases. That implication is false in general: equality corresponds to a right angle at `A`, not to isoscelesness. The answer never explicitly withdraws this wording. Thus the nonzero factor is repaired by a valid alternate construction-based justification, but a literal application of the rubric's ban on unretracted false claims should mark T014 as a proof-quality caveat, or withhold the fully clean complete-proof label. Final value `sqrt(305)/4` is correct. |
| T019 | **Complete proof upheld.** Its final coordinates give the same valid formula for `H`, the projection `P`, and the line/perpendicular-bisector equation for `T`, then expand to `AT^2=t^2-c^2`. It applies `T-B-C` to choose `MT=c+BT` and computes `sqrt(305)/4`. Earlier exploratory guesses are superseded by the final derivation; no contradictory final branch or value remains. |

## Conclusion

Three complete-proof passes are clean under the frozen criteria. T014's geometric derivation, nonzero cancellation, branch, and value are all recoverable and correct, and its own construction-specific sentence does justify the cancellation. Its claim that “because the triangle is scalene, `MA!=MB`” is inaccurate and unretracted. In fact, `MA^2-MB^2=AB·AC cos(A)`, so equality corresponds to a right angle at `A`, not to isoscelesness. If “no unretracted false claims” is applied literally to the entire generated answer, the original 4/4 complete-proof count should be reported with T014 flagged rather than as an unqualified clean pass. The frozen grade files remain unchanged pending the primary grader's decision.
