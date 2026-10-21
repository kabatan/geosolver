# Numeric derivation review: calibrated adjudication

I preserved the original review in `numeric-initial-ab-a.json`. This adjudication applies the precedent in `docs/research/transfer-reanalysis-2026-09-26/numeric-review-adjudications.json`: a correctly applied established result for the exact construction needs neither a theorem name nor a local proof. Tentative language alone does not defeat a retained true property and correct calculation. A question, generic pattern, or numerical fit alone does not invoke that result. I used `numeric-review-reference-compact.json` only to check the truth and applicability of properties actually stated in the answers.

| Case | Original | Strict | Calibrated | Decisive basis |
| --- | --- | --- | --- | --- |
| numeric-01 | invalid | invalid | **invalid** | Explicitly retracts the symmetry premise, then guesses its value (`205`, `389`). |
| numeric-02 | invalid | invalid | **invalid** | `JU=5` and the answer arise from a numerical guess, not a construction result (`392`, `449`). |
| numeric-03 | invalid | invalid | **valid** | Explicit exact-configuration known tangency result (`130–131`), then `PZ=12` and tangent–secant power yield `PX=6` (`159–161`). |
| numeric-07 | invalid | invalid | **invalid** | True H12 perpendicularity is posed as an alternative and then assumed from a generic pattern; numerical consistency is claimed as confirmation (`351`, `424–435`). |
| numeric-09 | invalid | invalid | **invalid** | The true DA15 diameter relation is only queried/hypothesized (`364`, `370`); the coordinate conversion also fails (`206–218`). |
| numeric-10 | invalid | invalid | **valid** | Explicit known tangency result under the given conditions (`224`), followed by correct tangent–secant calculation (`227–230`). |

The changed cases, **numeric-03 and numeric-10**, sit on the presentation boundary: their local tangency proofs are absent and the answers later use “assume,” so a strict self-contained-proof standard rejects them. Under the established numeric review standard, the answers retain a correct, exact specialized theorem application and valid arithmetic. The reference independently confirms that result; it does not add a missing premise to their text.

**numeric-07** is also a boundary case because the exact H12 perpendicularity is true. A generous reading could treat its “often lies” sentence as a tentative citation, yielding valid. I retain invalid: the answer frames the property as an open alternative, explicitly assumes it, and uses numerical agreement as supposed proof. The earlier false symmetry explorations were retracted, and I did not count those against the final answer. This follows the prior distinction between an asserted known H12 lemma and a guessed relation.

All six answer files were read in full in the initial review and decisive passages rechecked for this adjudication. No private condition mapping or model information was consulted. The JSON companion records line-numbered quotations, uncertainty, and coverage case by case.
