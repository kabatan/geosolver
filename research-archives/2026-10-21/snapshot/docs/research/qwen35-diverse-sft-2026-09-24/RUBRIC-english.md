# English-only study audit

The English problem text, user instruction, generated answer, and SFT teacher answer must all be in English. Greek symbols and mathematical notation are allowed. A non-English answer is not admitted as a teacher. Japanese runs stopped before any weight update and are excluded from the English comparison.

Source problem definitions and exact answer labels remain in the existing repository files. The model receives only the translated English problem and common English instruction; it receives no reference solution, target relation, or correct answer. The 37 English numeric templates retain every numeric placeholder from the corresponding approved Japanese template. Critical construction details and six translated proof prompts receive bilingual manual review.

## Material admission

Record separately: exact final number, true nontrivial configuration-specific relation, self-contained proof of its decisive step, actual use of the relation in the stated numeric problem, strong versus weak usefulness, output truncation, language, and origin file/hash. Admit only own-model visible final-answer passages satisfying every core requirement. Never use hidden thinking, a reviewer repair, or an evaluation output as a teacher. Count distinct configurations separately from numeric variants and repeated samples.

## Evaluation

The pre-existing numeric dev has 37 configurations, each sampled twice, with nine shape variants and 28 similarity variants. A `complete` answer needs the correct exact value, true relation, valid proof, and numerical application. Report the four components, truncation, per-configuration successes, and the two variant strata. This is within-configuration transfer, not new-configuration transfer.
Material collection, numeric dev, and proof evaluation use a 32,768-token output cap and a 45,056-token context; the earlier 6,144- and 16,384-token English collections were cancelled before admission. Every base and updated comparison uses the same cap within its task. Record all residual truncations separately.

The pre-existing six proof tasks are a separate evaluation, three designated transfer and three same-configuration. Score valid complete proofs without hint prompts, report actual training-configuration overlap, and do not merge their denominator with numeric dev. Both suites are research development evaluations, not a final untouched holdout.
