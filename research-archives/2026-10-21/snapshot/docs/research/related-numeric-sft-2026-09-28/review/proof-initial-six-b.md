# Anonymous AP01 proof review: cases 03–05

I read each problem and full model answer, including the long middle sections and final rewritten proofs. Grading follows `REVIEW_RUBRIC.md`: only a self-contained general proof receives 4. These are three responses to the same AP01 problem, not three independent geometry problems.

| Case | Score | Complete proof | Essential progress | Decisive gap |
| --- | ---: | --- | --- | --- |
| proof-03 | 2 | No | Correctly places A, P, N, and circumcenter O on the circle with diameter AO. | It never derives that F lies on that circle; it names that exact missing fact as a “known result” at line 507 and says it “can be shown” at line 530. |
| proof-04 | 2 | No | Correctly derives ∠BFC = 2∠BAC using the interior branch and identifies the needed angle involving P. | The final step at lines 525–528 asserts without derivation that F lies on circle APN. The preceding angle at F involving only B and C does not establish it. |
| proof-05 | 2 | No | Correctly derives ∠BFC = 2∠BAC and states a relevant cyclic-angle target. | Lines 527–530 claim a detailed trigonometric verification of ∠AFP = ∠ANP but never perform it. The coordinate attempt stops before computing the needed intersection/circle condition. |

The false auxiliary claims matter when assessing whether the missing step might already have been proved. In proof-04, the equilateral detour uses the wrong sign for a perpendicular-bisector slope at line 449. Its asserted counterexample is therefore false; that detour is outside the stipulated scalene domain and is not the reason for withholding a 4. In proof-05, line 36 incorrectly makes ∠ADB a right angle merely from D being on the perpendicular bisector of AB. Lines 42–47 also cross-multiply the sine rule incorrectly: BM = CM gives `sin(α) sin(C) = sin(γ) sin(B)`. In the valid sample A = 5+12i, B = 0, C = 14, the printed equality has sides approximately 0.49028 and 0.36825, and ∠ADB is approximately 115.84°. These are independent checks of intermediate assertions, not substitutes for a general proof.

The final cyclic-angle target itself is true in that sample, so the grading distinguishes a correct candidate relation from a derivation of it. None of the three supplies the latter. Full line-referenced evidence, incidental-error notes, uncertainty, and read coverage are in [proof-initial-six-b.json](proof-initial-six-b.json).
