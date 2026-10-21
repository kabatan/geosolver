# Diverse self-SFT: frozen audit rules

This rubric was written before inspecting generated baseline or training answers. The ten evaluation configurations and 27 material configurations are disjoint for this SFT. Some evaluation configurations appeared in older development probes; report those separately.

## Material admission

An answer is eligible only if all are true:

1. The answer is the same Qwen3.5-9B model's visible final response. Do not train on hidden thinking, a human solution, a stronger model's solution, or a reviewer repair. A continuous self-contained final-answer span may be extracted with recorded character offsets and hash.
2. Its committed exact numeric result matches the independently stored label. Parsing failure is `unresolved`, not a pass.
3. It states a nontrivial relation specific to the construction, with conditions. A restatement of the definition, a generic identity without a geometry-specific consequence, or a numerical coincidence is insufficient.
4. Its proof derives the decisive configuration-specific step from definitions, using valid standard theorems as needed. An unproved assertion of the target relation is insufficient. Verify critical algebra symbolically where practical and reject a relation with an exact counterexample.
5. It actually applies that relation to solve the stated numeric problem. Any unretracted significant mathematical error in the admitted span disqualifies it.

Record `numeric`, `true_relation`, `proof`, `use`, `strong_use`, `admit`, and a concise reason separately. Count source configurations and structural families, not just examples. Numeric relabeling of one derivation is not a new structure.

## Evaluation

Each of ten frozen configurations has two outputs from the same seed and sampling setup in every arm. Judge all 20 outputs, not the best answer only. The primary `complete` flag requires a correct numeric answer, a true nontrivial general relation, its valid self-contained proof, and actual use for that numeric answer. Record each component and truncation separately. A correct number with an invalid proof is incomplete. A correct relation/proof with an incorrect numeric substitution is incomplete.

Primary comparison is the per-configuration complete count, with the 20-answer total as a compact summary. Report the previously probed four evaluation configurations separately from the six without that prior pilot exposure. Do not call the latter never-seen by pretraining.

The older six-configuration proof suite and four-configuration discovery suite are secondary diagnostics only. They cannot replace the new frozen evaluation or be used to choose a checkpoint. Interpret a positive result as increased successful output frequency in this limited split, not proof of newly invented human-unknown geometry or of the absence of pretraining knowledge.
