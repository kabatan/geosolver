# Fresh2 numeric evaluation for the 38-row exploratory follow-up

## Scope

This folder freezes a second, distinct set of English numeric jobs for the next exploratory comparison of the 38-row `direct-multi`, `repeat`, and `balanced-qa` datasets. It reuses the same nine configuration IDs and transfer/retention roles as the primary near-transfer set: targets H03/H04/H08/H14/H15 and retention controls H01/H02/H07/H13. Every arm, including the untouched base if evaluated, must receive the same `eval_jobs.json` prompt text and per-job seed.

The five target configurations are absent from all three 38-row training datasets, as verified directly against their `source` fields and recorded in `construction_checks.json`. H03/H04/H14 are one correlated orthocenter/median-projection family; H08 is the tangent-circle/reflection probe; H15 is a separate three-reflection case. The four retention items are source-configuration controls, not independent transfer targets.

## Freshness and exact checks

Jobs were generated with the canonical geometry generator, its internal branch assertions, exact approved-template roundtrip checks, and the independent shape-answer formulas from `heldout-near-transfer/freeze_near_transfer.py`. Each visible novelty given lies outside the exhaustive finite projection of its original generator parameter domain. Each construction signature is absent from original v0-v3 training variants and the predefined similarity scales. `freeze_fresh2.py` replays the known fresh1 tuples in memory and rejects matching parameter/given/problem instances; fresh1 and repeat1 evaluation files and all generated model outputs were not opened. Since repeat1 keeps the fresh1 numerical constructions and changes only sampling seeds, the per-ID fresh1 instance distinction also prevents an exact numerical repeat1 collision. Fresh2 job seeds are regenerated deterministically from the fresh2 stage labels and checked against both corresponding fresh1/repeat1 seeds.

The evaluator-only `answer_key.json` is separate from all jobs and must never enter model context. The jobs retain the approved English numeric templates. `hashes.json` records the source and artifact digests. No training, model generation, or scoring was performed as part of this freeze.

## Use and interpretation

If this follow-up is run, compare untouched base and the three independently trained 38-row arms on the same nine jobs, decoding settings, and frozen seeds. Keep the scorer blind to arm. Record exact-value, useful-relation, proof, and correct-use components separately; complete success requires all components. Report H03/H04/H14 together, H08 and H15 separately, plus the four retention controls. These small, correlated, development-informed results are exploratory and cannot by themselves establish autonomous relation discovery or the broader research hypothesis. Do not select a checkpoint, prompt, or decoding recipe from these outcomes.
