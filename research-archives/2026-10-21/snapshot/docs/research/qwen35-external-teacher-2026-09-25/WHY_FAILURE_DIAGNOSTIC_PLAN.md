# Stage-localization diagnostics, fixed before fresh4 model outputs

The user asked why current external-teacher SFT fails to prove the bridge from
construction to useful relation. Existing blind grades identify where answers
fail, but do not establish a causal mechanism. These diagnostics separate four
capabilities on the same fresh4 numeric instances and must not enter any
held-out-transfer success count.

1. **Unhinted base:** the untouched Qwen3.5-9B base on all six fresh4 target
   jobs, already part of the bridge evaluation. This is the paired reference.
2. **Directly taught same-ID:** the previously trained all-37, one-epoch,
   LR 1e-5 adapter on all six identical unhinted jobs. It has seen one teacher
   answer for each H03/H04/H14 source ID. It tests whether this SFT dose can
   use an explicitly taught construction on a new numeric instance, not
   cross-ID transfer.
3. **General lemma supplied:** unchanged base on all six frozen
   `followup-relation-given-fresh4/eval_jobs.json` jobs. The supplied
   orthocenter-projection identity does not identify any target-specific point.
   The model still must derive the construction mapping and branch.
4. **Mapping claim supplied:** unchanged base on one fresh4 numeric instance
   per H03/H04/H14; the target-specific relation is stated as an unproved
   claim and must be justified from the construction. This probes whether
   finding the candidate relation, rather than proving it, is the obstacle.
5. **Mapping proof supplied:** unchanged base on those same three instances,
   with the decisive mapping argument included in the prompt. Score only
   downstream use, branch, and exact result as a conditional-execution
   diagnostic; the supplied proof is not independent model proof.

Use the same English problem wording, first-pass seeds, temperature 1,
top-p .95, top-k 20, presence penalty 1.5, cap 32768, and context 45056.
The additional cue-ladder jobs require a separate math/leakage audit before
GPU use. Preserve raw outputs and manually grade the decisive steps. Do not
read a diagnostic result to modify the already frozen bridge training data,
fresh4 prompts, or the primary blind rubric.

Interpret patterns cautiously: if a general lemma helps H04 but not H03/H14,
the hidden construction mapping remains a likely obstacle. If an unproved
mapping claim helps but the general lemma does not, relation search is
implicated. If only a supplied mapping proof helps, mapping proof is a stronger
bottleneck. If even the supplied proof does not help, downstream composition,
branch, or arithmetic are also limiting. If the directly taught all-37 adapter
still fails, one answer per source at this SFT dose may be inadequate even for
same-ID numeric generalization; that alone cannot distinguish dose, answer
format, and model capacity. Prompt interventions also change context and are
mechanism probes, not controlled estimates of SFT transfer.
