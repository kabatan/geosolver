# Dose-control recipe audit

**Conclusion:** `train_fit512.py` can be reused unchanged for both 128→512 continuations, provided each arm keeps its own frozen dataset and complete 128-update checkpoint. The checked-in `train_sft.py` hash matches the wrapper's expected hash (`f525e762…7b9857`). I reviewed trainer/wrapper code only; I did not inspect or edit dose-control data or `PROTOCOL`, and did not run a preflight, GPU job, or training.

## Chain and checkpoint semantics

`train_sft.py` directly accepts only 16 or 32 updates (`parameters`, lines 92–106), so a raw 512-update config will be rejected. `train_fit512.py` is the intended extension: it requires `updates=512` and a prior checkpoint at complete `global_updates=128`, then calls the frozen trainer's original parameter validator with `updates=32` while leaving the run spec at 512 (lines 22–28). The trainer therefore builds a 512-update order and processes only the suffix after the 128-step checkpoint. This wrapper is reusable on either arm as long as its 128 checkpoint comes from the same dataset as the 512 config.

| Arm | Required path | Evaluation role |
|---|---|---|
| Base | Frozen model, no optimizer updates | Baseline on the fixed 30 unused variant-10–12 prompts |
| Correct 128 | Existing correct A128 checkpoint | Existing-dose reference |
| Correct 512 | `train_fit512.py`, prior = correct A128 `final/` | Correct-label dose extension |
| Shuffled 512 | Fresh shuffled 32 → `train_continue.py` to 128 → `train_fit512.py` to 512 | Same-dose label-mapping control |
| Shuffled 128 | The shuffled chain's 128 `final/` checkpoint | Record its receipt/artifacts for chain integrity; do not evaluate in the initial comparison |

For the shuffled chain, `train_sft.py` produces the fresh 32 checkpoint; `train_continue.py` is specifically guarded for a complete 32-step prior and extends it to 128 (lines 24–40 of that wrapper). The resulting `final/` is a valid 128 prior for `train_fit512.py`. The latter always writes a final checkpoint; intermediate directories are made only at global steps listed in `save_checkpoints` (trainer lines 283–298). Saving step 128 during the 32→128 stage is optional because the stage's complete `final/` already records global step 128 and can be used for continuation.

Use distinct, new output directories for every stage: the run output directory and each checkpoint directory use `exist_ok=False`. For continuations, point `prior_checkpoint` to the preceding stage's complete `final/` directory. The wrapper's `updates` is the requested cumulative target; in the resulting receipt, `global_updates` is cumulative while `updates` is the number performed in that stage. Thus a 128→512 continuation should finish with `global_updates=512` and stage-local `updates=384`; a 32→128 continuation should finish with `global_updates=128` and stage-local `updates=96`. Use `global_updates`, checkpoint receipt status, and `optimizer_step_min/max` to identify the checkpoint, not stage-local `updates` alone.

## What the trainer guarantees, and what must be checked externally

- The training-parameter dictionary freezes seed, learning rate, accumulation, clipping, LoRA settings, token bounds, and related settings. A prior is rejected unless its receipt is complete and its frozen parameters, dataset hash, and model revision match the new run (trainer lines 92–106 and 235–245). The prior adapter, vLLM adapter, and optimizer files are also hash-checked, and the optimizer state is loaded (lines 239–257).
- Each optimizer update consumes four example presentations: the trainer divides each example loss by four, accumulates gradients, then clips and steps AdamW at each four-example boundary (lines 262–280). It uses AdamW at the frozen learning rate with zero weight decay and no scheduler (lines 256–257). On continuation, the previous optimizer moments and per-parameter step counters carry forward; this is a true continuation, not a fresh 512-step fit.
- `data_order` uses a local shuffle seeded by `seed + epoch`; `example-order.json` records epoch and row ID (lines 165–175, 211–215). The processed-prefix receipt hashes epoch/ID order. To make correct and shuffled order match, retain exactly the same row order and IDs and shuffle only targets. Same seed alone is not enough if row order changes.
- Resume checks also bind each continuation to its own dataset hash. Correct A128→512 must use the same exact correct-label dataset; shuffled 32→128→512 must use the same exact shuffled-label dataset throughout. A correct checkpoint cannot be used to start the shuffled chain, nor should it be: the trainer rejects the cross-dataset resume. The data hash distinguishes the two arms even though `processed_order_sha256` covers IDs/epochs rather than labels.
- The trainer validates numeric targets only as finite floats. It does not verify that a shuffled label came from the same `source_id`, that the shuffle is a bijection, or that a correct-label target is mathematically correct. Those are data-receipt checks outside this trainer. For a meaningful negative control, preserve prompts, IDs, source IDs, row order, and the exact multiset of correct target strings; record the target permutation and resulting file hash. Avoid fixed points where distinct target values permit a derangement, and report any unavoidable duplicate-value matches.
- A pure within-source target permutation preserves the overall label/token multiset, but changes which target lengths are paired with which prompts and can change token counts per optimizer step. The trainer averages each example's CE before accumulation, so the paired output length can affect sequence cost even though each example contributes one equally weighted loss. Check the fresh and continued receipts for identical row counts and the expected target-token totals; CPU `--preflight` can verify tokenization, no-truncation bounds, input hashes, and planned order before GPU work.
- **Preflight output-path gotcha:** the trainer creates `out/` with `exist_ok=False` before it checks `args.preflight`; preflight writes its tokenization/order/receipt files and returns only after that directory exists (lines 205–228). A real run cannot then reuse that same `--out` path; give preflight and training separate new directories. Also, trainer preflight returns before the full resume compatibility block (lines 231–245). The 512 wrapper does check that the prior receipt is complete at global step 128, but adapter/optimizer hashes, dataset hash, model revision, and processed-order prefix are fully validated only in the actual run before base weights are loaded. Do not treat a passing preflight as proof that resume artifacts are compatible.

The fixed seed makes the data order and initialization repeatable under the same environment, but this trainer does not enable deterministic-algorithm mode. Matching seed/order/settings controls planned exposures; it does not promise bitwise-identical GPU trajectories. The receipt records library versions and code/data/model hashes, which should be retained with each arm.

## Dose accounting and fair comparison

Assuming the 80-row numeric dataset used by the existing recipe, gradient accumulation 4 means 128 optimizer updates present 512 examples to the optimizer (6.4 dataset passes: six full passes plus 32 rows). A 512-update run presents 2,048 examples (25.6 passes: 25 full passes plus 48 rows). The correct 128→512 extension adds 1,536 presentations, or 384 actual optimizer updates. The shuffled path reaches the same total dose via 32+96+384 updates, so shuffled-512 and correct-512 have equal planned example count and update count. The optimizer trajectory differs because targets differ, as intended.

The requested four-arm comparison is interpretable as follows: base versus correct128 measures the original supervised run; correct128 versus correct512 measures additional correct-label dose; correct512 versus shuffled512 compares correct input-to-target mapping against a same-source target association at equal cumulative dose. Keeping shuffled128 out of the initial evaluations avoids adding another comparison while preserving that checkpoint as evidence of the chain. It also means this run will not estimate the shuffled-control effect at 128 updates.

Evaluate the same 30 unused variant-10–12 prompts with the same decoding settings and parser for base, correct128, correct512, and shuffled512. Keep all 30 out of both training datasets and record ID/prompt hashes showing disjointness. The main comparison is 120 generations per decoding setting. Report strict numeric correctness separately from relative error, and keep the four-arm planned analysis fixed before inspecting results.

## Audit basis

Relevant code locations: `docs/research/program-self-training-2026-09-26/train_sft.py` lines 92–106 (frozen settings/update gate), 146–175 (target tokenization and order), 178–202 (checkpoint and optimizer-step verification), 205–225 (planned run receipt), 231–260 (resume validation, seed, and optimizer restore), 262–298 (real update loop, intermediate/final saves); `docs/research/program-self-training-followup-2026-09-26/train_continue.py` lines 14–40; and `docs/research/proof-numeric-pilot-2026-09-28/train_fit512.py` lines 9–28.

## Completed-chain integrity audit

I independently checked the completed receipts, six corresponding configs, configured dataset file hashes, tokenization/order files, final adapter/vLLM adapter/optimizer artifacts, and prior-checkpoint links. **All requested training-chain integrity checks passed.** No evaluation outputs, predictions, or score files were opened; no training or GPU work was run.

The correct chain is old A32 → old A128 → new correct512; the shuffled chain is fresh shuffled32 → shuffled128 → shuffled512. All six stage receipts and final receipts are `complete`. The stage-local versus cumulative counts are:

| Chain stage | Stage updates | Global updates | Example presentations | Assistant target tokens processed in stage |
|---|---:|---:|---:|---:|
| Correct32 | 32 | 32 | 128 | 2,424 |
| Correct128 continuation | 96 | 128 | 384 | 7,287 |
| Correct512 continuation | 384 | 512 | 1,536 | 29,125 |
| Shuffled32 | 32 | 32 | 128 | 2,426 |
| Shuffled128 continuation | 96 | 128 | 384 | 7,286 |
| Shuffled512 continuation | 384 | 512 | 1,536 | 29,123 |

Both chains total 512 genuine optimizer updates and 2,048 example presentations. At every checkpoint horizon (32, 128, and 512), correct and shuffled `example-order.json` sequences match exactly by epoch and ID; each continuation is the exact prefix extension of its prior stage. The seed is 2026092701, all six frozen `training_parameters` dictionaries match, and model revision, model metadata hash, trainer, harness, and mapping-helper hashes also match.

The correct dataset hash is `778b87cfce6ea7271e971f8c727a5663468b783d21e7d21199bae7ccf46e26c9` at 32, 128, and 512; the shuffled hash is `9858b82131a70352ba5a890a0681282bb6a161b16fe642afa6457e51a8d451d8` throughout its chain. For every stage, the config hash matches its receipt, and the configured dataset and model-metadata files hash to the values recorded in both config and receipt. Correct and shuffled arms use distinct data hashes. The receipt-recorded tokenization and order hashes match their files; independently recomputed unique, planned, and stage-suffix target-token totals match the receipts.

The prior links are intact: correct128 points to correct32, correct512 to correct128, shuffled128 to shuffled32, and shuffled512 to shuffled128. Each child receipt's prior adapter, vLLM adapter, and optimizer hashes match its parent; the actual final artifact files match their recorded hashes. Every final optimizer receipt has `optimizer_step_min == optimizer_step_max == global_updates` (32, 128, or 512 as applicable), with 400 optimizer state entries.

The loss mask is “assistant target including EOS only.” Each dataset sums to 1,517 unique target tokens across its 80 examples. Cumulative exposure across the 2,048 presentations is 38,836 target tokens for correct and 38,835 for shuffled. This one-token difference is accounted for by the final partial epoch: both schedules have 25 full passes (37,925 tokens), followed by 48 examples contributing 911 correct versus 910 shuffled tokens. Every stage's token count was independently recomputed from its exact order suffix and matches its receipt.

As a limited check on the control construction, tokenization metadata shows the same IDs, source IDs, and per-ID prompt token counts across arms. All 80 target-text hashes change, while each source's multiset of target-text hashes is preserved. This supports a within-source target permutation; the audit did not adjudicate the mathematical correctness of individual target values. The receipts do not store a pre-update LoRA weight hash, so equal seed/config/base revision establish matching initialization settings but not an independent bytewise initial-weight proof.

Detailed per-stage hashes, token totals, order/prefix checks, and chain-link results are in [training-integrity.json](training-integrity.json).
