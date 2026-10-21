# Blind AP01 proof review: proof-00 through proof-07

All eight supplied JSON responses were read in full. Each ended naturally (finish_reason: stop). The grades judge the complete response, allowing self-corrections and checking the last proposed argument against the independent coordinate reference. No condition identity or numeric score was consulted.

| Case | Score | Decisive issue |
| --- | ---: | --- |
| proof-00 | 2 | The final continuity/uniqueness step does not establish that F is on circle APN; the location of F relative to that circle is the target claim. |
| proof-01 | 2 | The claimed known property is essentially AP01 and is not proved. No calculation locates 2F on circumcircle ABC. |
| proof-02 | 2 | The decisive statement that 2F is on circumcircle ABC is cited without derivation; the displayed angle relations alone do not prove it. |
| proof-03 | 2 | The claimed AF = FY is not derived from D and E. This is the decisive metric step. |
| proof-04 | 2 | The proof imports the desired cyclic angle equalities and also falsely infers that F lies on both segments BD and CE from interiority. |
| proof-05 | 2 | The required angle AFO = 90 degrees, equivalent to the goal, is asserted as a configuration-specific known property without proof. |
| proof-06 | 2 | Knowing the direction AF is a symmedian does not determine F's distance from A; the needed circle-incidence or radius condition is cited, not proved. |
| proof-07 | 2 | The claimed angle PFA = angle C is precisely the missing cyclicity step and is supplied only by a configuration-specific lemma citation. |

The common valid progress is the perpendicular-bisector angle relations. Several responses also derive angle BFC = 2 angle A or the homothety reduction to the circumcircle of ABC. None establishes the final incidence of F with circle APN: the missing step is replaced by a theorem citation, a continuity claim, or an angle equality that is equivalent to the requested conclusion. proof-06 has a useful additional derivation of the A-symmedian direction, but does not fix F on that ray.

The machine-readable record includes full file hashes, individual evidence excerpts, completion status, and case-specific gaps. No base/SFT grouping was performed.
