# Relation-given proof diagnostic (exploratory upper-bound control)

## Purpose and limits

This diagnostic gives each solver the correct construction-specific relation as a separate hint, then asks it to prove that relation from the geometry and use it to derive the final exact value. It tests proof execution and numerical application conditional on access to the right relation. It does **not** test autonomous relation discovery, self-generated learning, or whether SFT transferred the relation without help. Treat it as an oracle-assisted upper-bound/control diagnostic only.

The nine prompts are the five existing fresh target jobs (H03, H04, H08, H14, H15) plus the same four fresh retention controls (H01, H02, H07, H13). Their original numerical problem texts, per-job seeds, and construction variants are carried over unchanged from `../eval_jobs.json`; the relation hint is added in a separate field and in a separate labeled paragraph in the model message. No numerical answer, target result, or answer-key expression is included in any hint or model-facing prompt. The hints are intended claims to prove, not axioms to cite.

The three projection-family targets H03/H04/H14 remain one correlated lemma-family group. H08 (tangent-circle/reflection) and H15 (three-reflection midpoint) must be reported separately. Retention items remain descriptive controls. The source split and targets were already selected after inspection of development context; this is post-hoc exploratory evidence, not a confirmatory holdout.

## Frozen artifact and provenance

- `relation-given-proof-jobs.json` contains the nine model-facing prompts, relation hints, and original seeds. It was derived from `../eval_jobs.json` and `../answer_key.json` solely to select the intended lemma labels; the exact answer values were not copied into this artifact.
- Score against the existing `../answer_key.json`, which must remain evaluator-only and must never be included in model context. The hashes file records digests for both source files and this diagnostic's artifacts.
- The original `../eval_jobs.json`, answer key, prior result files, and any existing evaluation jobs are unchanged. No generation, training, scoring, or model-output inspection was performed while freezing this diagnostic.

## Comparison protocol

Use the same four conditions already specified in the parent `../PROTOCOL.md`: untouched base, 32-original, 36-multi, and 36-repeat. For every condition, run all nine prompts with the identical prompt text and each job's frozen seed. Inherit the parent protocol's decoding settings, conversation template, and output budget without condition-specific adjustments. This file defines prompts only; do not launch it as part of this freeze step.

Score each response blind to condition on separate binary criteria:

1. **Hinted-relation proof:** the response derives the hinted relation from the construction, including branch, sign, and nondegeneracy conditions where relevant. Repeating the hint is insufficient.
2. **Geometric proof/application:** it correctly connects the proved relation to the target quantity and uses all numerical givens correctly.
3. **Exact value:** the final value is mathematically equivalent to the evaluator-only answer key.

The complete diagnostic success is all three criteria. Report item-level paired outcomes and target groups; do not treat the nine items as independent samples. Do not count a success here as relation discovery or autonomous transfer. Compare these outcomes with the separately frozen no-hint prompts only as a conditional proof/application contrast; the no-hint and hint conditions answer different questions.

## Interpretation

A model that fails the hinted-relation proof has not established the relation even though it was told what to investigate. A model that proves and applies it successfully demonstrates conditional geometric reasoning for this instance, but that result alone cannot support a claim that the training caused transfer of the relation. Any positive outcome is bounded by the small, correlated, already-development-informed target set.
