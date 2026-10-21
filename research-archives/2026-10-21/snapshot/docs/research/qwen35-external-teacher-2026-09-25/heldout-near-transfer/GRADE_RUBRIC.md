# Condition-blind answer grading

Grade only the `final_text` field in the shuffled scoring packet. Do not inspect the condition mapping until all item grades are frozen. Use `answer_key.json` for exact targets and expected decisive relations. The five held-out IDs remain separated into H03/H04/H14 (one projection cluster), H08 (tangent/reflection), and H15 (three reflections). The four retention IDs measure same-configuration generalization.

For each answer, record four independent booleans and a concise mathematical reason:

1. **Exact value:** the final claimed value is equivalent to the answer key. A value guessed without derivation may pass this field only.
2. **Useful relation:** the answer states a true, nontrivial construction-specific relation that reduces the problem. Generic coordinate setup or an asserted final value alone is insufficient.
3. **Proof:** the answer derives its useful relation from the stated construction with the decisive calculation or geometric step and required branch/sign assumptions. Invoking a similarity, concyclicity, radical axis, or algebraic simplification without showing the crucial step fails this field.
4. **Use:** the valid relation is applied to the fresh givens with correct exact arithmetic and the proper branch. A numerical match obtained from a false relation fails this field.

`complete` is true only if all four fields are true. Grade the answer as a whole after explicit self-correction: an earlier discarded conjecture does not invalidate a later self-contained correct proof, but unresolved contradictions, unsupported final claims, or mutually inconsistent final derivations fail. Mark any case that needs second review as `uncertain` rather than silently resolving it. Preserve a short note on the specific missing/incorrect decisive step. Do not infer reasoning from raw text before a closing thinking marker or from the answer key.

After grades are frozen, join blind IDs to the mapping. Report paired base-versus-adapter outcomes by ID, metric component, and cluster. Keep response length and natural stopping as separate diagnostics. Do not use these answers to change a condition, checkpoint, prompt, or score threshold within this comparison.
