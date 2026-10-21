# Blind grade: H14

Graded the eight H14 entries in the shuffled packet using `answer_text` only and the frozen stage-localization rubric. I did not open the mapping vault, original arm directories, or prior grades.

The required construction link is **R is the foot from H to line AM**. This makes triangle AHR right-angled at R. The exact targets are:

- AH=13/4, AR=39/20: HR=13/5 and area=507/200.
- AH=17/3, AR=34√13/39: HR=17√13/13 and area=289/39.

| Blind ID | Finish / answer text | Mapping claim and proof | Downstream relation / proof | Exact value |
|---|---|---|---|---|
| T005 | stop / 29,583 chars | Not stated / no proof | Correct right angle at R / unsupported assertion | 507/200 correct |
| T009 | stop / 28,552 chars | Not stated / no proof | Wrong final right angle at A / no proof | 289√13/117 incorrect |
| T010 | stop / 24,629 chars | Not stated / no proof | Wrong final right angle at A; cyclicity claims unsupported | 289√13/117 incorrect |
| T011 | stop / 4,173 chars | Not stated / no proof | Incorrectly says A,H,R are collinear | 0 incorrect |
| T016 | stop / 4,964 chars | Not stated / no proof | Correct right angle at R / numerical pattern and vague lemma only | 507/200 correct |
| T020 | stop / 23,507 chars | Not stated / no proof | Wrong final right angle at A after contradictory guesses | 507/160 incorrect |
| T022 | stop / 4,238 chars | Not stated / no proof | Correct right angle at R / jump from reflection facts is unsupported | 289√13/78 incorrect; uses the wrong area legs |
| T023 | stop / 23,368 chars | Not stated / no proof | Correct right angle at R / key geometric step asserted, not derived | 289/39 correct after self-correction |

## Tally

- Correct mapping claims: **0/8**; valid mapping proofs: **0/8**.
- Correct downstream relation claims: **4/8**; valid downstream proofs: **0/8**.
- Correct exact values: **3/8**; complete proofs: **0/8**.

The four correct downstream claims identify the right angle at R, but none derives it from the construction. The three correct numbers therefore do not demonstrate transfer of the construction-to-foot relation: T005 and T016 use the right-angle claim without proving it; T023 also asserts the crucial locus and only repairs the arithmetic after contradictory intermediate computations.

The packet exposes answer text length in characters and finish reason, but not token counts. Exact completion token lengths are therefore unavailable under the blind-grading restriction; `grades-H14.json` records them as null rather than opening the mapping vault.
