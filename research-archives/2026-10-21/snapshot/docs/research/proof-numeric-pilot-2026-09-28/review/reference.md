# AP01 reviewer reference (proof and rubric)

This file is a reviewer-only mathematical reference. It is not teacher material or a model-facing hint.

## Exact coordinate proof

Take $A$ as the vector origin and put $u=\overrightarrow{AB}$, $v=\overrightarrow{AC}$, $U=u\cdot u=AB^2$, $V=v\cdot v=AC^2$, and $Q=u\cdot v$. Since angle $A$ is acute, $Q>0$. The noncollinearity of $A,B,C$ makes $u,v$ a basis. Write $S=U+V+2Q=|u+v|^2>0$, so $M=(u+v)/2$, $P=u/2$, and $N=v/2$.

Write $D=\lambda(u+v)$ and $E=\mu(u+v)$. The perpendicular-bisector conditions $DA=DB$ and $EA=EC$ give

$$
2D\cdot u=U,\qquad 2E\cdot v=V,
$$

so

$$
\lambda=\frac{U}{2(U+Q)},\qquad
\mu=\frac{V}{2(V+Q)}.
$$

Both parameters lie strictly between $0$ and $1/2$, so $D,E$ lie on segment $AM$. In barycentric coordinates relative to $A,B,C$,

$$
D=\frac{2Q\,A+U\,B+U\,C}{2(U+Q)},\qquad
E=\frac{2Q\,A+V\,B+V\,C}{2(V+Q)}.
$$

Consequently a point $F=\alpha A+\beta B+\gamma C$, where $\alpha+\beta+\gamma=1$, lies on $BD$ only if $\gamma/\alpha=U/(2Q)$, and lies on $CE$ only if $\beta/\alpha=V/(2Q)$. Therefore their unique intersection is

$$
(\alpha,\beta,\gamma)=\frac{(2Q,V,U)}{S},
\qquad
f:=\overrightarrow{AF}=\frac{Vu+Uv}{S}.
$$

All three barycentric coordinates are positive. Thus the stipulated interior location follows from the acute-angle condition; no extra placement assumption is needed for this calculation.

For any $X=xu+yv$, the circle through $A,P,N$ has equation

$$
|X|^2=\frac{Ux+Vy}{2}.
$$

Indeed, the left side minus the right side is a circle equation through $X=0,u/2,v/2$; these three points are noncollinear. For $f$, $x=V/S$ and $y=U/S$, hence the right side is $UV/S$. Directly,

$$
|f|^2
=\frac{|Vu+Uv|^2}{S^2}
=\frac{V^2U+U^2V+2UVQ}{S^2}
=\frac{UV}{S}.
$$

So $F$ is on the circle through $A,P,N$, as required.

An equivalent last step is to observe that $2F$ lies on the circumcircle of $ABC$, which is the image of the circle through $A,P,N$ under the homothety centered at $A$ with scale factor $2$. The circumcircle test for $2f$ is $|2f|^2=U(2V/S)+V(2U/S)=4UV/S$.

## Grading rubric

Assess logical completeness, not whether the submission uses these coordinates. A synthetic proof receives full credit if every angle or similarity step is established with the correct directed-angle/point-order convention.

| Level | Evidence required |
| --- | --- |
| 4 — correct proof | Derives the true location of $F$ (or an equivalent angle/ratio invariant) from both perpendicular-bisector conditions, then proves an exact concyclicity criterion for $A,N,F,P$. Handles nonzero denominators and any point-order claims it uses. |
| 3 — nearly complete | Correctly determines $F$ or an equivalent decisive relation, and identifies the right circle criterion, but leaves one straightforward algebraic verification or explicitly justified angle step unstated. No false premise. |
| 2 — substantive partial | Correctly derives both $DA=DB$, $EA=EC$ and usable formulas for $D,E$, or obtains one correct ratio for $F$, but does not establish the required cyclic relation. |
| 1 — limited partial | Gives a relevant valid observation (for example, $PN\parallel BC$, $DA=DB$, or $EA=EC$) without using enough of the configuration to constrain $F$. |
| 0 — unsupported/incorrect | No valid progress, or a purported proof depends on a false geometric claim or an unproved theorem that is exactly the target statement. |

For a binary correctness label, require level 4. Level 3 is insufficient if the omitted step could hide the central claim. An alternative complete proof need not explicitly discuss the interior assumption if its equations avoid point-order ambiguity.

## Pitfalls and edge conditions

- $AM$ is a median, not in general the angle bisector. Do not infer $\angle BAM=\angle MAC$.
- $D,E$ generally differ, and neither is generally the midpoint of $AM$. Their parameters are $U/[2(U+Q)]$ and $V/[2(V+Q)]$.
- The interior condition on $F$ does **not** ensure $F$ lies on both segments $BD$ and $CE$: $F$ is beyond $D$ on ray $BD$ when $U>V$, and beyond $E$ on ray $CE$ when $V>U$. Angle chasing that assumes both segment orders is invalid; use directed angles or prove the needed order.
- A statement such as “by the Humpty theorem, $A,N,F,P$ are concyclic” is circular unless that theorem is separately stated and proved in a form whose hypotheses are checked. Likewise, $PN\parallel BC$ or numerical examples alone do not prove cyclicity.
- The proof only needs $\angle A<90^\circ$ and a nondegenerate triangle; the additional acute angles, scalene hypothesis, and stipulated interiority are stronger than necessary. No division by $U-V$ is justified: the same identity also holds when $AB=AC$.
