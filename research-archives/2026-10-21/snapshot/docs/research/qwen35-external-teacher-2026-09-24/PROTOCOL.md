# External-teacher positive control (2026-09-24)

This is a feasibility diagnostic, separate from the research claim about learning from the model's own discoveries. An external solution may be used here. Any later self-generation study must start from the unmodified Qwen3.5-9B base model, not this adapter.

## Frozen comparison

- Base: `Qwen/Qwen3.5-9B`, revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`.
- Main SFT: at most one fully audited English answer per training configuration, targeting all 37 configurations. Source problem and exact label come from the `v0` rows of `training_variants.jsonl`. The frozen English user prompts come from `material-original-jobs-en.json`.
- Check the answer's exact result, construction-specific useful relation, proof of its decisive step, and actual use of the relation. Check nondegeneracy, sign, branch, and uniqueness conditions. Independent numeric examples may reject a claim but cannot establish a general proof. A local typo is recorded; it is not silently inherited. Reject incomplete answers rather than adding a plausible but unproved lemma.
- Candidate answers may use synthetic, coordinate, vector, or mixed proof. Record auxiliary constructions and decisive lemmas separately from proof representation. Teacher method is not chosen using model evaluation outcomes.
- Main dose: rank-8, alpha-16 LoRA, learning rate 5e-5, assistant-only loss, one example/update, two epochs, and maximum prompt-plus-answer sequence length 8192. Abort on overlength; do not truncate a proof. One final checkpoint is evaluated. This dose is 74 updates if all 37 are admitted, more updates than the prior 40-update run.
- If fewer than 37 teachers pass audit in the available collection window, run a clearly labelled partial-coverage diagnostic only. Report missing configurations and reasons. Do not pad coverage with numeric relabelings or duplicate proofs.

## Evaluation boundaries

- Numeric development set: the existing 37 `eval_variants.jsonl` records, 2 generations each. All 37 share configuration IDs with the full training set; this measures new numeric/shape conditions within learned configurations, not unlearned-configuration transfer.
- Proof development set: the existing six `humpty_proof_evaluation_v2` prompts, 2 generations each. EV02, DU01, OB01 are close or compositional transfer questions, while AP01, N01, N02 are same-configuration proof questions. They were already used for development. A proof question supplies its conclusion and does not test spontaneous relation selection plus numeric application.
- Compare exact numeric value, true useful relation, self-contained decisive proof, and actual numeric use separately. `complete` requires all four. Track proof validity and auxiliary construction separately in proof tasks. Count configurations and decisive-lemma families; repeated samples are not independent structures. Include paired improvements and regressions, and detect loss of numeric performance.
- Before interpreting any proof result, audit *actual admitted teacher text* against each proof task's target lemma and proof. Record: same statement/proof, reused lemma, new combination, or no material overlap. If an answer directly supplies an evaluation proof, reclassify that evaluation accordingly.
- Use unchanged base outputs only if job hash, model revision, seed, sampling, generation cap, and grading rule agree. Generate the updated adapter under exactly the same 32768-token cap, 45056-token context, non-thinking mode, temperature 1, top-p .95, top-k 20, and presence penalty 1.5.
- Label this as a positive-control diagnostic. Even positive results cannot establish autonomous self-discovery, pretraining novelty, or broad geometry generalization. A later integrated unseen numeric evaluation would be needed to test relation selection, proof, and application together on new configurations.

## Provenance and corrections

`benchmarks/humpty_proof_evaluation_v2/manifest.json` hashes an older version of `training_problems.jsonl`, so it is retained as historical evidence and is not the active training/evaluation manifest. `manifest.json` in this directory records hashes of the exact files used here.

The prior admitted H07 self-answer in `train-multiconfig-en.json` omits `r^2` when expanding two circle equations. It is not silently reused. Its final relation may survive subtraction, but this positive control requires a fresh independently audited answer. DA13, DA16, and DA17 also have `source_claim_only` in `revisions.json`; their central statements need independent proof before admission.

## Exploratory dose check

After the fixed two-epoch main run showed severe errors on the proof probes and the first numeric configurations, `train-protocol-low-dose.json` was frozen before completion of the numeric evaluation. It uses the same 37 answers, one epoch and learning rate 1e-5. This is a dose-sensitivity diagnostic with no checkpoint selection; its outcome is exploratory because the development proof tasks had already been inspected. Interpret it separately from the main result.
