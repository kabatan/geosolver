# Why the construction-to-relation step fails

## Finding

The current evidence localizes the main failure to proving that an indirectly constructed point is the familiar orthocenter projection. It does **not** show a general inability to use the projection formula once the foot is explicitly defined, and it does not establish why the model fails causally. In particular, H03 mostly fails to identify the right relation at all; H14 often states the right projection relation and gets the downstream arithmetic right, but does not derive that relation from its circle construction. H04 is the useful contrast: its prompt gives the orthocenter foot directly, and the model sometimes carries that relation through the perpendicular-bisector calculation.

This report uses only already unblinded first-pass, repeat1, leave-one-out, and fresh2 answers and the audited teacher data. Fresh3 and bridge outputs are excluded. No model was run and no GPU was used.

## What the answer grades isolate

The rubric grades exact value, useful relation, proof from the construction (including decisive signs and branches), and correct use as separate fields. “Proof” therefore measures the bridge in these problems, not just general fluency.

Across first-pass, repeat1, and fresh2, there are 36 answers on H03/H04/H14: 13 state the exact value, 13 state a useful relation, 12 apply a relation correctly, but only 3 prove the relation and only 3 are complete. The breakdown by configuration is more diagnostic:

| Target | Answers | Exact | Relation | Proof | Use | Complete | Observed pattern |
|---|---:|---:|---:|---:|---:|---:|---|
| H03: angle-bisector circle meets median | 12 | 0 | 1 | 0 | 0 | 0 | Usually asserts the wrong center or projection; one answer states the right local projection relation but has a sign error and never proves the final circle-center relation. |
| H04: perpendicular bisector through an already-defined foot | 12 | 9 | 8 | 3 | 8 | 3 | Often reaches the right relation/value; many proofs cancel a factor without establishing from acuteness that it is nonzero. Complete answers occur, but in different arms on different passes. |
| H14: two circles define a common point | 12 | 4 | 4 | 0 | 4 | 0 | Several answers state that the point is the foot from H and compute the area correctly, but do not connect that claim to D, E, P, Q and the two circles. |

Thus H03+H14 have **0/24** construction-derived proofs, although a few answers contain a correct relation or exact downstream result. This is not solely a strict-grader effect: H03 commonly has a false relation, while H14's missing construction link is explicit in the answer notes. The stricter proof gate does matter for H04: correct relation and arithmetic commonly survive while the branch/nonzero justification does not.

The leave-one-out check agrees with this split but is tiny: omitting H03 yielded 0/1 on H03; omitting H14 yielded 0/1 on H14; omitting H04 yielded 1/1 on H04. H04's leave-one-out solution had access to sibling projection examples. It is evidence that the easier exposed-foot problem can be solved without its own row, not evidence of transfer across all three constructions.

## The mathematical steps the model must bridge

### H03: recover a projection, then recover a second circle

The teacher overlap audit finds that H01 teaches the metric for the foot of H on a median: with `BC=2m`, `M=(0,0)`, and `A=(u,v)`, the projection parameter is `m²/(u²+v²)`. H03 hides that foot inside a different construction. A valid proof must:

1. Derive the signed product of the internal/external angle-bisector feet on `BC` (the relevant product is `+m²`).
2. Use the circle through `A,K_a,L_a` to show its second median intersection has parameter `m²/AM_a²`.
3. Use the altitude equations and the acute-angle branch to identify that point as the foot from H to the median.
4. Show the three feet lie on the circle with diameter `HG`, so its center is `(H+G)/2`; with O as origin this gives `OZ=(2/3)OH`.

Observed answers often skip from the statement to `Z=H`, the midpoint of `OH`, or the nine-point center. In first-pass B018 (32-original), the answer names the correct local projection parameter, but its signed/Vieta derivation is inconsistent and it never proves the circle center. In first-pass B031 and repeat1 B016, a wrong sign for the angle-bisector-foot product leads to an incorrect projection and center claim. These errors occur before the final arithmetic.

### H14: invert the whole construction before using the same projection fact

H14 shares the projection endpoint but reaches it through a longer construction. The proof must show that D and E lie on the reflected circumcircle, that P and Q are their images under inversion centered at M, and that the second common point of circles BPM and CQM is `I(A)`. Only then can one use the altitude equations to establish that R is the foot of H on AM and choose the correct segment branch.

First-pass B025 and repeat1 B024 state the correct `AR ⟂ HR` relation and obtain the area, but leave the inversion/circle-to-R step asserted. Other answers guess that R is a reflection or antipode of H, or put the right angle at the wrong vertex. Across the 12 H14 answers, four have the exact value and four state the correct relation, yet none proves the relation from the construction. That is a direct construction-link gap, rather than a failure to perform the last metric calculation.

### H04: a control where the projection is exposed

H04 defines P as the foot from H to AM in the prompt. It therefore does not ask the solver to recognize a point hidden in a circle or inversion construction. The H01 projection formula is directly applicable; the remaining work is to impose `TA=TP`, use the order `T-B-C`, and compute the length. The three complete H04 answers in the 12 paired answers appeared under first-pass 36-multi, repeat1 36-repeat, and fresh2 base. No trained condition consistently owns the success. Among incomplete responses, the common precise defect is cancellation of a factor without proving it nonzero from acuteness. This is a weaker and more local proof gap than H03/H14.

H08 and H15 should not be pooled with this projection cluster. In the same three scored sets, H08 has 0/12 complete; its target requires a tangent/reflection angle identity absent from the audited teacher lemmas. H15 has 0/12 complete; its decisive three-reflection midpoint lemma is absent. They show that nearby methods do not guarantee transfer, but they are separate mathematical bottlenecks.

## What the training data can and cannot explain

The primary held-out training file contains 32 v0 answers from 32 source configurations. It excludes H03, H04, H08, H14, and H15 as whole source IDs. Its relevant direct projection supervision is H01: the point is already defined as the foot from H, and the answer derives its projection parameter. The audited overlap file identifies H01 as a direct ingredient for H03 and H14, but does not identify any training answer that derives H03's circle-to-foot mapping or H14's inversion-to-common-point mapping. H04 also overlaps H01's half-base-square term and DA05's `MD·ME` term.

The later fresh2 datasets add six rows for 38 total: direct multi-instance examples, matched repetitions, or balanced relation-verification questions built from other sources. They still exclude the target IDs and do not add either missing construction bridge. None of the three SFT arms completed a held-out target in fresh2; the base completed H04. This is consistent with missing intermediate-step supervision, but it does not prove that this is the cause. The comparison is small, development-informed, and does not isolate training dose, proof format, or capacity.

Other candidate explanations have different levels of support:

- **Supported as an observation:** generation is stochastic. H04's complete answer moves among multi, repeat, and base conditions across passes, so one success cannot be attributed to a stable data-arm effect.
- **Disfavored as the main explanation:** truncation. All first-pass/repeat1/fresh2 answers stopped naturally below the 32,768-token cap; fresh2's longest answer was 12,352 tokens.
- **Possible, not causal evidence:** answer-policy/style mismatch. The projection-family evaluation median is about 9,474 completion tokens, while the matched 36-row teacher answers have medians about 606–616 tokens. Outputs contain extended false starts and corrections. Yet H04 complete solutions are also long, so verbosity alone does not explain the bridge failures.
- **Still unresolved:** whether one epoch at low learning rate is too little to learn the relevant abstraction, whether proof composition exceeds current reasoning reliability, or whether the answer format directs probability toward plausible claims instead of verifiable intermediate steps. The existing comparisons do not separate these factors.
- **Not a scoring artifact alone:** independent second reviews retained the H04 cancellation failures, and the recurring H03/H14 omissions are substantive missing derivations. A permissive self-correction rule can affect isolated cases, but cannot supply a missing circle or inversion proof.

## Stage-localization diagnostic to identify the bottleneck first

The current unhinted outputs localize the problem only broadly. A small, no-retraining evaluation with controlled hints would distinguish the stages. For each of H03 and H14, use the same checkpoint, numerical instance, decoding settings, and two fixed generation seeds for three prompt versions:

1. **Unhinted full problem:** reproduce the current end-to-end task.
2. **Bridge claim to prove:** give only the candidate intermediate statement and ask for a proof from the original construction. For H03, ask to prove that the circle's second median intersection is the orthocenter's projection; for H14, ask to prove that the common point of the constructed circles is the foot of H on AM. Do not provide the coordinate derivation.
3. **Bridge supplied as a premise:** state that same intermediate relation as given, then ask for the remaining circle-center or area argument and the exact result.

Run H04 with its original exposed-foot prompt and a fresh H01-style exposed-foot item as controls. Blind-grade (a) relation identification, (b) proof of the bridge, (c) downstream proof, (d) branch/sign, and (e) exact use separately. If version 2 fails but version 3 succeeds, the construction-to-relation proof is the localized bottleneck. If version 2 succeeds but version 1 fails, integration/search is the likely issue. If version 3 also fails, downstream proof competence is implicated. Use new independently checked numerical instances for any later transfer claim; these already-used IDs can only diagnose, not confirm.

For an immediate CPU-only follow-up, preserve the current frozen grades and have a second reviewer label each answer's first failed proof step using the five categories above. This does not require model inference, cannot establish causation, and will test whether the present failure localization is robust to a finer rubric.

## Evidence files

- Frozen split and scoring design: `heldout-near-transfer/PROTOCOL.md` and `heldout-near-transfer/GRADE_RUBRIC.md`.
- Teacher/source-step overlap audit: `heldout-near-transfer/lemma_overlap.json`.
- First-pass/repeat1 item grades: `qwen/.runtime/qwen35_external_teacher_20260925/scored-near-transfer-first-pass/item-pairs.json` and `scored-near-transfer-repeat1/item-pairs.json`.
- Fresh2 item grades: `qwen/.runtime/qwen35_external_teacher_20260925/scored-fresh2/item-pairs.json`.
- Leave-one-out grades: `qwen/.runtime/qwen35_external_teacher_20260925/scored-loo/joined-grades.json`.
- Existing detailed reviews: `SECOND_SEED_PROJECTION_FAILURE_ANALYSIS.md` and `SECOND_SEED_TANGENT_FAILURE_ANALYSIS.md`.
