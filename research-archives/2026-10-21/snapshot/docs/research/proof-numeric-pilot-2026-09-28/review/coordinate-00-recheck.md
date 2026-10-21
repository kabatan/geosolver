# coordinate-00 independent recheck

Final grade: **3/4, incomplete** (revised from 4). The response derives the correct coordinates of (D,E,F) and the correct circle through (A,N,P). Its last equality is recoverable from displayed expressions, but the response ends by appealing to numerical verification instead of completing that equality. More importantly, its branch statement and two slope divisions fail the explicit sign/branch standard of the prompt and reviewer rubric.

Write (S=u^2+v^2>c^2), (K=S-c^2>0), (S_1=S+uc), and (S_2=S-uc). Acuteness gives (|u|<c), hence (S_i>S-|u|c>c^2-|u|c>0). The response's (t_D=K/(2S_1)) and (t_E=K/(2S_2)) are positive. Also

\[
2S_1-K=(u+c)^2+v^2>0,\qquad
2S_2-K=(u-c)^2+v^2>0,
\]

so both (t_D,t_E<1). For its parameterization (r(t)=t(u,v)), the ray **from (A) through (M)** has (t\leq1), and these intersections in fact lie between (A) and (M). Merely checking (t>0), as the response does, does not establish membership in that ray. It states the wrong branch rule even though the calculated points happen to satisfy the right one.

The two denominators used as line slopes are indeed nonzero, but this is likewise unstated. From the displayed (D,E),

\[
Ku+2cS_1=2S_1(c+t_Du)>0,
\qquad
Ku-2cS_2=2S_2(t_Eu-c)<0,
\]

because (0<t_D,t_E<1) and (|u|<c). This also validates the subsequent cancellation. These are necessary checks for the specific path the response chose, not a new geometric theorem.

For completeness of this audit, its final exact circle identity is true. With (T=u^2-v^2), the displayed left numerator simplifies to

\[
4u^2v^2c^4+(S^2-c^2T)^2
=S^4-2c^2S^2T+c^4S^2,
\]

using (T^2+4u^2v^2=S^2). Its corrected right numerator is

\[
S^2\{4v^2c^2+(S-c^2)^2\}
=S^4+c^4S^2+c^2S^2(4v^2-2S)
=S^4-2c^2S^2T+c^4S^2.
\]

Thus the final algebra is a routine missing step, and the underlying result is correct. I assign 3 rather than 4 because the written proof does not meet the protocol's explicit branch/sign requirement; I do not reduce it to 2 because the correct exact formulas and all terms of the decisive equality are supplied, allowing independent verification without inventing a new relation.
