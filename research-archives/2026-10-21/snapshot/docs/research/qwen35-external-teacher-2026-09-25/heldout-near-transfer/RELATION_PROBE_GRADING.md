# Relation-only probe grading (2048-token exploratory rerun)

Grade the four model conditions blind for each of the nine frozen `relation-only-jobs.json` prompts. The model was asked for one nontrivial general relation useful for the requested quantity, its necessary branch/nondegeneracy conditions, and one decisive reason. It was told to avoid substituting the numerical givens, avoid the final value, and use at most 180 English words.

Record independent booleans:

- `relation`: at least one mathematically true, construction-specific relation that materially reduces the requested quantity. A generic theorem or a relation that cannot help determine the target is insufficient.
- `branch`: every sign, ordering, intersection-choice, or nondegeneracy condition needed for the stated relation is correct. Harmless omitted assumptions already explicit in the problem do not invalidate it.
- `reason`: a decisive derivation from the construction, with enough equations or geometric correspondences to rule out merely guessing the relation. A plausible assertion without the decisive step fails.
- `instruction`: no final numerical answer or numerical substitution, English, and at most 180 words. Count words in the visible answer after stripping math markup; use the answer's natural word count and note borderline cases.

`complete_relation` is the conjunction of the first three, independent of instruction compliance. An answer may self-correct: assess the final coherent claim and its final derivation, and record any substantial contradiction in the note. Record `uncertain` if a mathematical claim cannot be resolved from the frozen key and proof notes. Do not open the condition mapping or raw adapter-specific outputs before grades are frozen. This probe diagnoses relation recall/justification only; it cannot count as a complete numeric proof or as autonomous discovery.
