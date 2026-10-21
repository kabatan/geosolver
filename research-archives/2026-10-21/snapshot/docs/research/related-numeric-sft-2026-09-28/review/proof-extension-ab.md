# AP01 proof review — extended natural stops

The self-contained general-proof rubric applies to both answers. I read each full response; neither is a complete proof.

| Case | Score | Complete proof | Assessment |
| --- | ---: | --- | --- |
| proof-00 | 2 | no | Correctly obtains $\angle BFC=2A$, then fails to connect it to the required angle involving $FP,FN$. The trigonometric bridge is asserted and contains a reversed median sine ratio (lines 367–388). |
| proof-01 | 3 | no | Correctly derives a general vector expression for $F$ (lines 119–159) and reduces the goal to $2F$ on the circumcircle of $ABC$ (lines 484–501). It omits the final circle substitution and ultimately cites the sought specialized relation; the omitted algebra is short and independently checks out. |

For proof-01, writing $B=|\mathbf b|^2$, $C=|\mathbf c|^2$, $q=\mathbf b\cdot\mathbf c$ and $S=B+C+2q$, the **answer's own** formulas simplify to $F=(C\mathbf b+B\mathbf c)/S$. If $O$ is the circumcenter with $A=0$, then $O\cdot\mathbf b=B/2$ and $O\cdot\mathbf c=C/2$, giving $F\cdot F=BC/S=O\cdot F$. Hence $2F$ is on the circle through $A,B,C$. This independent check establishes that the model's general derivation reaches a true core, but it is not a self-contained finished proof because the model never presents that calculation. Score 3 is a boundary judgment: a strict reading of its final unsupported theorem appeal would assign 2. The final angular claim $\angle BAF=\angle CAM+B$ is false for interior $F$ and is separate from the valid vector core. The JSON records line evidence, read coverage, and other errors.

No private condition mapping or GPU work was used.
