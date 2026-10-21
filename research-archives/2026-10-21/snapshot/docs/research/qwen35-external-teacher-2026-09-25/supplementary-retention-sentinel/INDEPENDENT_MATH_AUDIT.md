# Independent math audit: supplementary retention sentinel

CPU-only audit of `eval_jobs.json` and `answer_key.json`, cross-checked against the construction witnesses and the source configuration records. No model-generation outputs were inspected and no GPU was used.

| ID | Key | Independent check |
|---|---:|---|
| DB02 | `21/2` | The angle conditions give `BP=AB^2/BC` and `CQ=AC^2/BC`. With the midpoint conditions, the resulting lines `BM` and `CN` meet at the keyed distance. This agrees with the source answer `6` scaled by `7/4`. |
| DA18 | `56` | The construction gives `FD·FE=BF^2` and `∠DFE=120°`. With `FD+FE=119/4`, the cosine rule yields `DE=105/4`; adding the three sides gives `56`. |
| DB06 | `245/192` | In the source construction, the angle conditions place `X` and `Y` at the diagonal midpoints and `XY^2=5/12`. The fresh instance scales every length by `7/4`, so its squared answer is `(49/16)(5/12)=245/192`. Each angle condition varies monotonically along its stated diagonal, so the interior point is unique when it exists. |
| H12 | `105/8` | The construction relation is `PQ ⟂ AC`. The givens give `MV^2=PM^2−PV^2=49/16`, so `MV=7/4`; they also give `QV^2=QM^2−MV^2=1225/4`, so `QV=35/2`. The stated same-side, farther branch yields `PQ=QV−PV=105/8`. |
| HX01 | `8√11/3` | For the fixed generator parameters `(BC, ax, ay_num)=(8,3,7)`, coordinates `A=(3,3√7), B=(0,0), C=(8,0)` give `AC=2√22`, `AL=3√11`, and `J=(11/3,−√7/3)`. Thus `J` lies on ray `AL` and `AJ=8√11/3`. Equivalently, the verified construction relation `AJ·AL=AC^2` gives this length. |
| DA03 | `441/4` | The hidden tangent relation gives `AK^2=BK·CK`. Since `K,B,C` occur in that order, `CK=BK+BC=567/4`; hence `AK=√((343/4)(567/4))=441/4`. |
| DA07 | `63/2` | The source construction supplies `MN ∥ XY`. With `A,M,X` in that order, `AX=AM+MX=189/4`, so triangles `AMN` and `AXY` have scale `AX/AM=27/4`. Therefore `XY=(27/4)(14/3)=63/2`. **Parallelism is essential**: collinearity of `A,M,X` and `A,N,Y` alone would not justify the homothety or the answer. |

## Interpretation and limitations

The seven keys are mathematically consistent with the problem statements and construction witnesses. I found no ambiguity that invalidates an individual exact answer. DA07's keyed relation should be understood as the construction's `MN ∥ XY` theorem, together with the given order `A–M–X`; the abbreviated phrase “A-centered homothety” depends on that parallelism.

This sentinel is a **result-informed retention diagnostic**, not evidence of transfer to a new configuration family. The six similarity-transformed items keep their source construction and change only the numeric scale. HX01 extends one parameter in the same construction family. The selected source IDs were also chosen using earlier untouched-base results. Those features are disclosed in the protocol and mean any outcome should be reported separately from the frozen held-out near-transfer comparison.

The model-facing jobs contain the English problem and the common instruction, without a supplied solution. The exact answers and expected lemmas are in the separate grader-only key; the metadata in the job records the diagnostic role but does not expose an answer.
