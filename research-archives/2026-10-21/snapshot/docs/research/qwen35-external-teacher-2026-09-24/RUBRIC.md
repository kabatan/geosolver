# External teacher admission and outcome rubric

## Candidate admission

For every training configuration, record a candidate even if unresolved. A complete candidate is admitted only when each item is independently checked:

1. **Numeric:** The exact requested value follows from the stated givens and matches the frozen training label. A lucky or memorized final number is insufficient.
2. **Relation:** A true, nontrivial statement about the construction is given, including material conditions. A definition, a single numeric coincidence, or a generic identity without a construction-specific consequence is insufficient.
3. **Proof:** The decisive step of that relation is derived from the original construction and valid standard theorems. A named Humpty/Dumpty fact, an unexplained similarity or cyclicity, and a computation specialized to one witness do not establish a general statement.
4. **Use:** The relation is in the actual dependency chain producing the numeric answer. Mentioning it beside a separate calculation is insufficient.
5. **Cases:** Check existence, nondegeneracy, sign, order, and branch assumptions that affect the answer. An unproved case selection is disqualifying.

Tag proof representation (synthetic, coordinate, vector, mixed), auxiliary construction, decisive lemma, teacher source, word/token length, and the exact reason for acceptance or rejection. No evaluation output or proof-evaluation target is a training source. Previously admitted self-answers are not silently reused, especially the H07 answer with an algebraic typo.

The external teacher may use a researcher sketch or receive human repair, but that fact must be recorded. This phase tests Qwen's ability to learn from valid worked solutions. It does not test whether Qwen independently generated those solutions.

## Numeric development outcome

For each of 37 configurations, two paired generations from unchanged base and the final SFT adapter use identical English prompts, seeds, sampling, and 32768-token completion cap. Record exact value, true useful relation, self-contained decisive proof, actual use, output truncation, and method. `complete` is the conjunction of the first four. Report per-configuration 0/2, 1/2, 2/2, paired gains and losses, and distinct lemma families. The full-training arm makes all 37 configurations seen structures; this set tests new numerical/shape conditions within them.

## Proof development outcome

For each of EV02, DU01, OB01, AP01, N01, N02, two paired generations use identical frozen conditions. Score a complete proof of the stated conclusion and tag whether a new auxiliary point or relation was actually introduced and used. Do not count a theorem name or conclusion without its decisive proof. The first three are near/compositional transfer probes; the last three are same-configuration proof probes. Compare actual teacher content with each target proof before interpreting a gain. None of these asks the model to select an unstated relation and use it for a numerical unknown.

## Interpretation

Keep correctness and capability retention separate. A rise in proof success with a fall in numeric correctness is not success on the complete research objective. These development sets have been used in prior iterations. A positive result is a reason to conduct a new integrated unseen numeric test and a separate self-generation study, not evidence of autonomous discovery by this externally taught adapter.
