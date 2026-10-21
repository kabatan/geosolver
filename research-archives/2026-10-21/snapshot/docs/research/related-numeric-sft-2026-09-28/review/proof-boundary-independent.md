# AP01 proof-boundary review

**Score: 2/4. Complete proof: no.** The answer makes real general progress in coordinates, but it never proves that its constructed intersection lies on the required circle. The final attempt substitutes an unsupported property for that step and uses a specific angle relation that fails on a valid configuration.

## Independently checked results

With the answer's convention (A=0, B=\mathbf c, C=\mathbf b), the perpendicular-bisector equations are (X\cdot\mathbf c=|\mathbf c|^2/2) and (Y\cdot\mathbf b=|\mathbf b|^2/2). Substitution verifies its

\[
D=k(\mathbf b+\mathbf c),\quad k=\frac{|\mathbf c|^2}{2(\mathbf b\cdot\mathbf c+|\mathbf c|^2)},\qquad
E=m(\mathbf b+\mathbf c),\quad m=\frac{|\mathbf b|^2}{2(|\mathbf b|^2+\mathbf b\cdot\mathbf c)}.
\]

Its line equations at lines 133–139 are correct. Solving them gives

\[
u=\frac{2m-1}{k+m-1},\qquad v=\frac{2k-1}{k+m-1},\qquad
F=\frac{k(2m-1)}{k+m-1}\mathbf b+\frac{m(2k-1)}{k+m-1}\mathbf c.
\]

I verified the (v) expression directly rather than relying only on the stated symmetry. For acute (A), (\mathbf b\cdot\mathbf c>0), hence (0<k,m<1/2) and the common denominator is nonzero. This is useful general progress, but the answer never substitutes these coordinates into a circle equation.

The homothety observation at lines 436–440 and 484–490 is also correct: the map centered at (A) with ratio (1/2) sends the circumcircle of (ABC) to the circle through (A,P,N). It makes the goal equivalent to (2F\in(ABC)); it does not establish that condition.

## Essential gap and false step

At lines 471–473, the answer says a full coordinate proof is lengthy and invokes a “known lemma.” At line 501, it says the key fact “can be shown” by trigonometric Ceva or coordinate verification, but carries out neither. This is the central implication, not routine algebra left between a stated identity and its immediate simplification. The vector approach stops after finding (F), labels it messy, and never writes the circle-membership criterion.

The final formal attempt asserts at line 503 that \(\angle BAF=\beta+B\), with \(\beta=\angle CAM\). This is false. For an exact counterexample, take (A=(0,0), B=(4,0), C=(1,3)). Its side lengths are (4,\sqrt{10},3\sqrt2), and the dot products testing the angles at (A,B,C) are respectively (4,12,6>0), so the triangle is acute and scalene. The verified vector formulas give (k=2/5,m=5/14) and (F=(28/17,24/17)=(4/17)A+(5/17)B+(8/17)C), so (F) is strictly interior. Here \(\tan\beta=6/7\), \(B=45^\circ\), and \(\tan\angle BAF=6/7\); since both \(\beta\) and \(\angle BAF\) are acute, \(\angle BAF=\beta\), not \(\beta+B\).

The answer does retract the earlier power claim (BF\cdot BD=c^2/2) after noticing that (D) is not the other circle intersection (lines 345–356). It does not replace that route with a valid argument. Lines 508–512 question the later angle reasoning but do not repair it, and lines 517 and 525 return to an unsupported uniqueness/property assertion and conclusion.

The tentative conversion to (N,P) at line 163 also has a factor-of-two error: its parenthesized coefficients do not follow from (\mathbf b=2N,\mathbf c=2P). The answer does not use that expression later; its preceding (\mathbf b,\mathbf c) coefficients remain correct. The angle-order explanation at lines 79–81 is also unsound, although the problem itself already assumes (F) is interior.

## Boundary and evidence

The AP01 rubric assigns 3 only when the essential general derivation works and the remaining issues are local notation or branch checks. That threshold is not met: membership of (2F) in the circumcircle is not derived, and the replacement angle assertion is false. Score 4 is therefore also excluded because the answer is not self-contained. Score 2 reflects the valid intersection computation and the substantial central gap; the answer goes beyond score 1's useful partial calculations by explicitly setting up the correct homothety equivalence, while failing to prove its decisive condition.

Quoted evidence from `proof-01.md`:

- Lines 155–159: the answer states a candidate vector for (F), then computes its two coefficients; these expressions check out independently.
- Lines 471–473: “Since a full coordinate proof is lengthy, we invoke the property…” and “the concyclicity is a known lemma.” This is the missing proof.
- Lines 501–503: the answer defers the core verification and asserts \(\angle BAF=\beta+B\), which the exact counterexample above disproves.
- Lines 163–164: the tentative (N,P) conversion and its subsequent coefficient comment expose the local scaling slip.

**Read coverage:** I read all 527 lines of `proof-01.md` and the full `REVIEW_RUBRIC.md`. I did not read any other review JSON/Markdown, private condition table, or evaluation output. Confidence is high that the answer is incomplete and below score 3; score 2 follows the rubric's “major gap” category.
