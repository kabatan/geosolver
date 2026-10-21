# Projection-cluster failure analysis: first pass and repeat1

## Scope and result

This note uses the frozen first-pass and repeat1 joined grades for H03/H04/H14 (12 projection answers per pass), the corresponding blind answers, the grading notes, and the comparison protocol. It does not modify the frozen data or scores. The family is a single lemma cluster, not three independent targets.

| Pass | Base | 32-original | 36-multi | 36-repeat |
|---|---:|---:|---:|---:|
| First pass | 0/3 complete | 0/3 | 1/3 (H04) | 0/3 |
| Repeat1 | 0/3 | 0/3 | 0/3 | 1/3 (H04) |

Across the 24 scored projection answers, only two are complete: first-pass H04 in 36-multi (B027) and repeat1 H04 in 36-repeat (B013). No H03 or H14 answer is complete. The arm-level component counts are in [first-pass counts](../../../qwen/.runtime/qwen35_external_teacher_20260925/scored-near-transfer-first-pass/counts.json) and [repeat1 counts](../../../qwen/.runtime/qwen35_external_teacher_20260925/scored-near-transfer-repeat1/counts.json); per-answer judgments and reasons are in the corresponding joined-grade files.

## Failure modes

- **Relation missing or replaced by a false one.** H03 outputs repeatedly jump to a center claim without deriving it: examples assert `Z = H`, `Z = O`, or the nine-point center. Some additionally put `P_a` on the altitude rather than the median, or use the wrong sign for the internal/external bisector feet product. First-pass 32-original is a partial exception: it states the correct per-vertex projection relation, but its signed derivation is inconsistent and it never derives the required center `Z = O + (2/3)(H − O)`.

- **Relation found, construction link omitted.** H14 demonstrates this most clearly. First-pass 36-repeat and repeat1 32-original/36-repeat state the correct `AR ⟂ HR` relation (so `R` is the projection of `H` onto `AM`) and apply Pythagoras to get the exact area. Their answers do not derive that relation from the constructed circles; the inversion mapping through `D, E, P, Q` to `R` is asserted or guessed. Other H14 answers confuse the right-angle vertex (`AH ⟂ AR`) or claim a false reflection/antipode.

- **H04 has an identifiable proof and branch bottleneck.** Base answers use the unsupported `AT = BT + BM`. The first-pass 32-original response reaches the right number after a wrong orthocenter sign and a boundary-value guess. In repeat1, 32-original, 36-multi, and base reach the correct value and relation, but divide by a factor without validly excluding its zero case using acuteness. These are derivation/branch failures, not arithmetic failures.

- **No isolated arithmetic-only error stands out.** Wrong final values in this cluster follow from a false relation, sign/branch error, or unsupported center claim. Where a correct relation is available, the exact arithmetic is generally correct.

## H04 complete answers share one mechanism

The two complete H04 answers use the same coordinate chain as the trained H01 projection example:

1. Put `M = (0,0)`, `B = (−m,0)`, `C = (m,0)`, `A = (u,v)`, derive `H = (u,(m²−u²)/v)`, and project to `P = (m²/AM²)A`.
2. Apply `TA = TP`, or equivalently the perpendicular-bisector midpoint condition, to get `2tu = AM² + m²`; then `AT² = t² − m²`.
3. Use the stipulated `T, B, C` order to convert this to `AT² = BT(BT + BC)`, then substitute the givens.

B027 (first-pass 36-multi) and B013 (repeat1 36-repeat) both eventually provide this derivation despite long discarded false starts. The success is therefore not evidence of different mechanisms in the two data arms. It is one stochastic success in each arm on different passes. The protocol says 36-multi adds numerical H01/H07 variants while 36-repeat adds exact v0 copies; both keep 36 rows, seed, and optimizer matched. The projection cluster's complete answer switches arms between passes, so this sample does not show a stable benefit from either addition regime. H04 also shares the half-base-square term with DA05, limiting attribution to H01 alone. See [first-pass H04 review](FIRST_PASS_H04_CASE.md) and the [near-transfer protocol](heldout-near-transfer/PROTOCOL.md).

## Next positive-control data changes

1. **Conditional decomposed projection-bridge control.** If leave-one-out answers show a recurring gap at the bridge to the common lemma, compare two teacher formats on the same permitted sibling source IDs and numbers. In the treatment, separate each source into (i) deriving its mapping to the common projection lemma, (ii) proving the lemma including its nondegeneracy and branch conditions, and (iii) using it for the downstream numeric result. In the matched control, use the usual complete solution for each same source. Keep example/token budgets, presentation counts, seed, and training settings matched; evaluate on newly authored numerical instances across fixed generation seeds. For each rotation, exclude **that rotation's held-out ID** from all training text; the other two sibling IDs are permitted. Lock every new evaluation job before training. A single leave-one-out sample cannot establish a stable gap, so this remains an exploratory targeted intervention.

2. **Conditional inversion-bridge control.** Only if a leave-one-out audit on non-held-out inversion sources shows the same recurring construction-to-image gap, compare verified midpoint-centered inversion examples (deriving the decisive image and branch) against ordinary circle-power proofs, matched by source IDs, example count, and token budget. Exclude orthocenter projections and the `D,E,P,Q,R` construction or its right-angle conclusion. Evaluate on a newly authored inversion sibling set; retain H14 only as an already exposed exploratory comparison.

The existing split is explicitly post-hoc exploratory in its [protocol](heldout-near-transfer/PROTOCOL.md), so new confirmation should use untouched sibling targets rather than treating these three items as fresh holdouts.

## Output-length diagnostic (inference, not a cause finding)

CPU token counts from [the training token audit](heldout-near-transfer/multi-token-audit.json) give median teacher-answer lengths of 616 tokens in 36-multi and 606 in 36-repeat. Across the 72 first-pass/repeat1 evaluation generations, the median completion is 9,169 tokens; the projection-only median is 9,474, and all 72 finish naturally with `stop`. The evaluation generations therefore run about fifteen times longer than the teacher answers and often contain extended conjecture/correction sequences. This is consistent with a supervision-style mismatch that could amplify unsupported claims, but these data do not establish causation: both complete H04 proofs are also long.
