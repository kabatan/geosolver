# Integrity audit: numeric SFT study

Snapshot: 2026-09-28 07:56 UTC. This was a read-only audit of frozen inputs, configs, training receipts/order, amended evaluation manifests, and generation receipt metadata. No model was loaded, no GPU was used, and no runtime input or running pipeline file was changed. Full evaluation outputs and scores are not audited.

## Findings

**The frozen training inputs and both training chains are internally consistent. Evaluation is still in progress.** Every hash in `main-freeze.json` (4 entries), amended `data-freeze.json` (14 entries), and the saved pre-amendment freeze (12 entries) matched at the audit snapshot. The dataset is 80 rows across 10 construction types, 8 each. Each target is finite, numeric-only `.17g`, and matches its provenance target. Each user message is the frozen English `TRAIN_PREFIX` plus the provenance problem. No AP01 proof or answer is present in the training set.

The four configs use the same pinned Qwen3.5-9B revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, model metadata hash, dataset hash `778b87cfce6ea7271e971f8c727a5663468b783d21e7d211bae7ccf46e26c9`, and recipe: BF16, LoRA r=8/alpha=16/dropout=0, the same ten projection modules, AdamW at `5e-6` with zero weight decay, gradient accumulation 4, clip 1.0, target CE including EOS only, and thinking disabled. Sequence/target limits are 8192/4096 tokens.

| Chain | Fresh-base stage | Continuation | Final optimizer steps | Examples presented |
| --- | --- | --- | --- | --- |
| A (`2026092701`) | 32 updates; no prior adapter or optimizer | 96 additional updates; loaded hashes match the 32-update adapter and optimizer | min=max=128 | 512; all 80 IDs appear 6–7 times |
| B (`2026092901`) | 32 updates; no prior adapter or optimizer | 96 additional updates; loaded hashes match the 32-update adapter and optimizer | min=max=128 | 512; all 80 IDs appear 6–7 times |

For both seeds, all 512 loss events match the configured deterministic order and example IDs/token counts; the 32-update order is exactly the prefix of the 128-update order. The saved processed-order hashes match the recomputed prefixes. Adapter and optimizer hashes differ between the two fresh chains. Recomputed first/last presentation loss means agree with `training-summary.json`: A 2.481171→2.045134, B 2.481058→2.045695; all 80 rows have a lower last-presented loss in each seed. These are training-context CE measurements, not evaluation accuracy.

The frozen main manifest has 24 jobs: the eight untrained numeric construction types H02, H03, H08, H12, DA15, DB01, DB08, DB16 at two inference seeds each; four AP01 proof seeds; and four easy retention questions. Its source IDs and job IDs do not overlap the training set. The separate exact-answer key covers the 16 numeric transfer and 4 easy jobs. AP01 proof jobs intentionally have no numeric answer key. The generation driver reads no answer key, and rejects jobs containing `target` or `answer_exact`.

## Diagnostic prompt amendment

The original record remains above; the later amendment is documented in [DIAGNOSTIC_PROMPT_AMENDMENT.md](DIAGNOSTIC_PROMPT_AMENDMENT.md). Before any diagnostic output existed, the 20 diagnostic prompts were changed to use the exact training numeric-only prefix. The pre-amendment jobs, answer key, and freeze were retained and their saved hashes matched. The current diagnostic jobs have 10 `trained_example` prompts identical to their corresponding training messages and 10 `new_shape` prompts mapped to each type's heldout `variant-09`; all ten new-shape IDs are disjoint from training IDs. The amended jobs, amendment document, and amendment script hashes match the current data freeze. Main jobs and their separate freeze remain intact.

The previously prepared conditional 10-job `exact-prompt` set has prompts identical to the amended `trained_example` half of the diagnostic. If its trigger condition is later met, reuse those diagnostic results rather than generate duplicates.

## Evaluation status and un-audited work

At the snapshot, base main and seed-A main each had 24/24 first-pass 32k outputs. Their receipts matched the frozen job hash and model revision; seed A's adapter hash matched its trained final adapter. There were 1 and 3 `finish_reason=length` outputs respectively. Seed-B main was running with 8/24 outputs; one of the eight had `finish_reason=length`. Observed job IDs contained no answer fields. This verifies receipt/manifest integrity for those outputs, not their mathematical correctness or explanations.

The following remains un-audited: the remaining 16 seed-B main jobs; all three 20-job diagnostic runs; any main or diagnostic 81k/131k extensions selected after all initial generations; final-cap selection; numeric scoring; and anonymous proof/derivation review. At the snapshot, extension output directories, `generation-complete.json`, and `final-cap-by-job.json` did not exist. No evaluation conclusion should be drawn from this interim state.

For a post-run integrity pass, recheck both freeze manifests' SHA-256 entries, then ensure every final-cap-selected output file exists for each arm and each main/diagnostic job, all corresponding receipts are complete and point to the frozen jobs hash/model revision/adapter hash, and no output has a mismatched ID. Keep any remaining `finish_reason=length` count separate from completed answers. Score and review outputs require a separate audit after generation is complete.
