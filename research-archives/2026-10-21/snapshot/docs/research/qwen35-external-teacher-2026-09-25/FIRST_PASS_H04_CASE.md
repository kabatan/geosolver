# First-pass H04 paired case (fresh1)

The same English H04 prompt, construction, numerical givens (`BT=3/2`, `BC=10`), seed, and 32,768-token cap were used for the untouched base and all three independently trained adapters. All four answers naturally stopped. The four responses were graded with condition hidden before the following mapping was opened; H04 received a second independent blind review with the same complete-solution judgments.

| Condition | Final value | Why the proof score differs |
|---|---|---|
| Base | `13/2` | Claims `AT=MT=BM+BT`; `TA=TP` does not imply `AT=MT`. |
| 32-original | `sqrt(69)/2` | Hits the right number via a power/limit heuristic but calls it a boundary value and does not establish the projection and perpendicular-bisector identity. |
| 36-multi | `sqrt(69)/2` | Derives `H=(u,(m²-u²)/v)` with `M=(0,0)`, `B=(-m,0)`, `C=(m,0)`, `A=(u,v)`; hence `P=(m²/(u²+v²))A`. From `TA=TP`, obtains `2tu=u²+v²+m²`; therefore `AT²=t²-m²`. The `T,B,C` order gives `t=-(BT+m)`, so `AT²=BT(BT+BC)=69/4`. Complete under the frozen rubric. |
| 36-repeat | `13/2` | Asserts an incorrect projection/orthocenter identity and then derives the false `AT=MT=BM+BT`. |

The successful answer contains some discarded false starts and a nonessential illustrative existence check whose particular coordinates do not verify every acute-angle condition. The decisive coordinate derivation above is separate from that check and is valid. It is one stochastic response from one numeric instance and one training seed. The fixed second-seed pass and the sibling-configuration leave-one-out arms are needed before inferring a stable SFT effect. H04 also overlaps DA05 through a half-base-square term, so this result alone cannot attribute the mechanism uniquely to the added H01 numerical variants.
