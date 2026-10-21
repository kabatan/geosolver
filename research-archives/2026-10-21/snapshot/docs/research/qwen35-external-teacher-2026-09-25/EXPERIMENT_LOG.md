# External-teacher SFT transfer diagnostics (2026-09-25)

## Research question

This is a positive control for a later study of whether Qwen3.5-9B can acquire a construction-specific geometric relation from its own independently checked work and transfer it. External worked proofs are used **only** to test whether learning and transfer are feasible. Success here cannot establish autonomous discovery. An eventual self-generated study must restart from the unmodified base model.

## Evidence boundaries

- The existing 37 `v0` teachers are English, one answer per configuration. The earlier two-epoch 5e-5 LoRA gave 0/12 valid proofs on six reused proof-development questions, versus 6/12 for base. Its 37-configuration numeric development run was interrupted after 64/74 responses.
- Existing proof-development questions and numeric `d1` variants are **development data**. Repeated experiments on them are exploratory diagnostics, not an independent confirmation of transfer. The 37 numeric `d1` variants share configuration IDs with the teacher set.
- Count paired samples and configuration/lemma clusters separately. A valid proof needs the decisive construction-specific step, not merely the stated conclusion. Numeric completeness requires correct exact answer, true useful relation, proof, and its application. Record numeric retention alongside proof success.

## Frozen diagnostic arms

1. **Low dose:** all 37 original teachers, 1 epoch, 1e-5, rank 8; script and protocol in the 2026-09-24 folder. This changes both seed and dose from the earlier main run, so it is a diagnostic, not a clean single-factor ablation. Evaluate the same six proof questions and a prespecified nine-configuration numeric sentinel.
2. **Same learning rate, two epochs:** all 37 teachers, the low-dose seed and 1e-5 learning rate, two epochs. Compare with arm 1 to isolate repetition at this learning rate. Its protocol was frozen before the arm-1 proof run completed. Evaluate with the same development questions and numeric sentinel.
3. **No-EOS loss:** all 37 teachers, original seed/2 epochs/5e-5, with loss on all visible answer tokens except the final EOS. The protocol and modified training driver are in this folder. This isolates whether explicit EOS training is the main cause of short post-SFT responses. Evaluate the same proof questions and numeric sentinel. It does not by itself test data diversity.
4. **Held-out near transfer:** train new adapters from base with whole configuration IDs H03, H04, H08, H14 and H15 excluded. The other 32 external teachers remain. A separate set of fresh, construction-verified English numeric problems for the five held-out IDs will be frozen before its evaluation. H03/H04/H14 are one projection-lemma cluster. H08 is a tangent-circle/reflection near-transfer case from H07; H15 uses a different three-reflection midpoint lemma and is an independent exploratory case, not a second H08-family replicate. This is exploratory because the teacher set and configuration families have already been inspected during earlier work.
5. **Multiple worked instances linked to arm 4:** prepare additional audited English teachers for H01/H07 v1/v2 from the same proved general relations. Compare `32 originals + H01/H07 v1/v2` with `32 originals + matched H01/H07 v0 repetitions`, using the same seed, presentation count and update count. Keep `v3` and the earlier `d1` out of training. Evaluate the five held-out IDs with the same fresh problems in both arms. H01's numeric changes are invisible shape changes to the model and already have a high base ceiling, so it is a relation-fidelity probe. H02/H13 variants are supplementary within-ID diagnostics. Token counts, order, losses and grad norms must be reported; equal updates alone do not equalize effective gradient information.

Each generation uses the existing English task prompt, non-thinking mode, cap 32768, context 45056, temperature 1, top-p .95, top-k 20, presence penalty 1.5, and two paired samples. Keep the model revision, job hash, exact labels, receipts and manual grading reasons with the outputs. No target proof or label is used for teacher creation or adapter selection.

## Decision rule

Call the present positive control promising only if an adapter improves valid unseen-configuration solutions or proofs while preserving substantial numeric competence, with the improvement traced to a correct learned relation rather than style or answer length. A result on reused development prompts motivates a fresh check; it does not count as independent transfer. Report negative and mixed arms, including regressions.

## Mechanism diagnostic, initial three adapters

`diagnose_policy.py` was run after the low-dose proof generation completed, comparing the unchanged base, original 74-update adapter and 37-update low-dose adapter. Its machine-readable output is `qwen/.runtime/qwen35_external_teacher_20260924/policy-diagnostic-high-low.json` (96 rows; peak allocated GPU 18.47 GiB). This is a **small, exploratory** teacher-forced probe on H01/H02/H13 and common prefixes from base H01 numeric and EV02 proof answers.

The mean NLL of the exact training teacher answers fell in all three configurations under the 74-update adapter (H01 1.424→0.542, H02 1.672→0.930, H13 1.644→0.895). The adapter therefore did fit the teacher strings. The first-token distribution nevertheless shifted sharply from base (base-to-high KL 8.64 nats for H01 numeric and 4.62 for EV02 proof; base-to-low KL 0.072 and 0.056). On the chosen *base-answer prefixes*, EOS probability was extremely small for all arms at 128–1024 tokens. This does not rule out early stopping on the high-dose model's own divergent prefixes, but does **not** support a simple global increase of EOS on the same continuation.

Direct formula-string NLL and the A/B recognition probe were mixed: high dose favored a plausible false H01 formula by per-token NLL even as its A/B log-odds for the correct formula increased; H02 A/B recognition worsened. Different formula tokenizations make raw NLL gaps descriptive only. These probes cannot replace generated proof or numeric grading. The data support fitting plus prompt-time policy drift, without yet identifying whether an EOS-specific or broader answer-policy shift causes the failures.

## Completed low-dose proof development evaluation

The 37-example, one-epoch, 1e-5 adapter generated all 12 answers with the unchanged 32,768-token cap and matched jobs/seed/sampling. All 12 ended naturally. Median completion length was 9,463 tokens, versus 7,845 for base and 803 for the original 74-update adapter. The independent strict review in `qwen/.runtime/qwen35_external_teacher_20260924/eval-proof-low-dose-en-32k/manual-grades.json` found **5/12 valid**, versus **6/12 base** and **0/12 high dose**. The low-dose valid answers were OB01 2/2, N01 2/2 and N02 1/2. EV02, DU01 and AP01 remained 0/2. OB01 was already 2/2 at base; N01/N02 are same-configuration tasks. This is retention of much baseline proof behavior, not a detected gain in new-configuration transfer. N02-1 was re-reviewed and marked invalid because its final similarity correspondence cannot yield its claimed side ratio.

## Frozen near-transfer comparison, 2026-09-25

The [protocol](heldout-near-transfer/PROTOCOL.md) and input hashes are fixed. The main comparison uses the unchanged base plus three independent low-dose adapters: 32 original teachers excluding H03/H04/H08/H14/H15, 32 plus H01/H07 v1/v2 numerical counterfactuals (36 rows), and 32 plus exact H01/H07 v0 repeats in the same four added positions (36 rows). All use 1 epoch, LR 1e-5, seed 2026092431, rank 8/alpha 16. The 36-row arms each have 32 source IDs and no target source. Their assistant-span token totals including EOS are 21,854 and 21,742 respectively, a 112-token difference. The audit and protocols are in `heldout-near-transfer/multi-*`.

Nine fresh English evaluation jobs were frozen before these adapter evaluations: H03/H04/H14 as one projection-lemma cluster, H08 as a tangent-circle/reflection near-transfer case, H15 as an independent three-reflection case, and four same-configuration retention controls. This split is exploratory, since family selection was informed by earlier work. A condition-blind scoring packet will be made from all four arms. A separate [leave-one-projection-ID protocol](heldout-near-transfer/leave-one-projection-id/PROTOCOL.md) freezes three easier sibling-teacher checks, each with exactly one held-out target and four retention controls.

The 37-example low-dose numeric sentinel completed 18/18 generations with natural stops and no truncation, median 8,311 completion tokens (range 4,968–12,825). Strict grades and a matched `final_text` comparison are in `qwen/.runtime/qwen35_external_teacher_20260924/eval-numeric-low-dose-sentinel-en-32k/base-comparison.md`. Base→low-dose: exact final value 9/18→10/18; useful relation 9/18→8/18; proof 6/18→6/18; correct application 9/18→8/18; all-four complete 6/18→6/18. DA01 improved from 0/2 to 2/2 complete and DA18 from 1/2 to 2/2, while DB02 fell 2/2→0/2 and DB06 1/2→0/2. This is mixed same-configuration behavior, not evidence of unseen-configuration transfer.

The unchanged-base fresh nine-job evaluation completed with the frozen job hash `b50c8520ee294b1f338620a46a443b48d12bd345a714e8aa791b7972e4acfd46`; all nine generations ended naturally. The raw answers remain unopened pending a four-condition blind scoring packet. All three independent SFT runs then completed successfully: 32-original had 32 updates and 19,936 answer-span tokens; 36-multi had 36 updates and 21,854 tokens; 36-repeat had 36 updates and 21,742 tokens. Training receipts and adapters reside under `qwen/.runtime/qwen35_external_teacher_20260925/train-near-{32-original,36-multi,36-repeat}`. Their adapter SHA-256 values are respectively `b15bd73d4cec2d7ba4e9920ada0f228f7948f064db2ce07019a20adc1244b6af`, `7d015bbedf11181964a462420f0f1e1085bd53343c9eac93a4cf76bf654d6f29`, and `187fa2e372debdb3f0121c5be546ac8925aad332d7c89e26433fcc9bead57193`; each passed 400/400 adapter tensor reload-equality checks. The 32-original evaluation is running before the two 36-row evaluations. Do not inspect any answer text until all four conditions finish and the blind packet is frozen.

After training, the three receipt dataset hashes were recomputed from the frozen training files and matched exactly. The respective row/source counts are 32/32, 36/32, and 36/32. None contains any of the five held-out target IDs (H03/H04/H08/H14/H15).

The first-pass 32-original evaluation completed all nine jobs with the identical frozen job hash, one sample per job, and natural `stop` on every answer. The completion lengths in fixed target/control order were 8,724, 12,795, 8,897, 12,595, 10,554, 3,154, 9,618, 9,930, and 9,401 tokens; none reached the 32,768 cap. No answer content has been opened or graded. The 36-multi condition was launched next, with the same jobs and decoding settings.

While the comparison runs, a separate nine-job `heldout-near-transfer/followup-fresh2/` set was frozen for any later 38-row data-regime comparison. An independent auditor checked all nine numerical keys and branches against the construction. Its H08 instance deliberately has `AC ≠ AP`; a future proof scorer must use the full two-tangent-circle equations and acute-angle branch, not transplant the simplifying `AC = AP` step from fresh1. This fresh2 set remains exploratory and is not part of the current four-condition scoring packet.

Three candidate 38-row follow-up training files were also prepared without using model outputs: `relation-discrimination-v2/train-38-direct-multi.json` (32 original teachers plus H01/H07 v0/v1/v2 worked answers), `train-38-repeat.json` (matched v0 repetitions), and `train-38-balanced-qa.json` (three true and three false relation-verification problems). They have 32 distinct source IDs and no current held-out target source. Assistant target tokens including EOS are 22,757, 22,645, and 22,917 respectively. The balanced QA targets were revised after independent audit to include self-contained coordinate, branch, and application proofs in each row; the auditor then rechecked all six and found the mathematical labels, full proof steps, and cross-file hashes consistent. Their current dataset hashes are `9184877c357dca76c5630f3c1ff0eb8250d2105eb0da844f3a55dd1255738bbf`, `67c4836e9c89054b15b46587683a58ce6049dfdaadfafe441b7593c41a86bf7a`, and `da66b08c3d83ddd50bc7c1802030bee0da497b0821fb3378ef0cf07229326291`. These arms remain **untrained** as the main first-pass comparison proceeds. The pre-frozen fresh2 job file has hash `9947444ede2b19d1122f1a7be0e830299cc12b91c90edd24e94f8cca17670e71`.

The 36-multi first-pass evaluation completed all nine jobs with the same frozen hash and natural `stop` for all nine. Completion lengths in target/control order were 7,895, 6,171, 12,290, 10,835, 10,612, 5,608, 9,109, 9,863, and 9,538 tokens; none reached the cap. Its answer content remains unopened. The 36-repeat control was launched next with the same nine jobs, cap, and sampling settings.

## First-pass blind near-transfer result

All 36 responses (nine jobs × four conditions) ended naturally below the 32,768-token cap. A condition-blind shuffled packet was graded on exact value, useful relation, proof, and correct use before opening the condition mapping. The six primary grade-file SHA-256 values are frozen in `qwen/.runtime/qwen35_external_teacher_20260925/blind-near-transfer-first-pass/primary-grade-freeze.json`. H01 and H04 received independent second reviews with the same complete-solution judgments. The joined scores and item pairs are in `qwen/.runtime/qwen35_external_teacher_20260925/scored-near-transfer-first-pass/`.

| Condition | Projection cluster H03/H04/H14 complete | H08 | H15 | Four retention controls complete |
|---|---:|---:|---:|---:|
| Base | 0/3 | 0/1 | 0/1 | 1/4 |
| 32-original | 0/3 | 0/1 | 0/1 | 1/4 |
| 36-multi | 1/3 (H04) | 0/1 | 0/1 | 1/4 |
| 36-repeat | 0/3 | 0/1 | 0/1 | 1/4 |

The 36-multi H04 response derived the orthocenter-projection parameter and perpendicular-bisector equation, handled the `T,B,C` ordering, and obtained `sqrt(69)/2`. Both blind reviewers accepted it as a complete proof. The 32-original H04 response only hit the final value by an invalid heuristic; the 36-repeat H14 response stated the right relation and value but did not prove the construction's decisive inversion step. H03, H08, and H15 had no complete answer under any condition. On retention, H01 was complete in all four conditions; H02, H07, and H13 were complete in none. The signal is one exploratory sample in one projection-family configuration, below the predeclared two-of-three projection-cluster threshold. The aggregate near-transfer comparison is within one complete solution of zero, so the frozen sequential rule triggers the second-seed pass for **all four conditions and all nine jobs**; do not select only H04.

The 36-multi and 36-repeat runs had nearly matched supervised answer tokens (21,854 vs 21,742), mean update loss (1.4773 vs 1.4815), and sum of preclip gradient norms (42.999 vs 42.532). At the four matched added slots (updates 6/27/28/35), multi's losses were 1.392/1.254/1.264/1.250 and repeat's were 1.419/1.313/1.304/1.289; multi's gradient norms were 1.420/0.954/0.954/1.299 and repeat's were 1.456/0.985/0.983/1.340. Thus the single H04 success cannot simply be ascribed to more updates or a visibly larger added-slot gradient norm, but it also cannot establish that numerical diversity caused the gain from one sample.

The relation-only 512-token cap diagnostic had length-truncated answers, so `RELATION_PROBE_CAP_REVISION.md` froze a uniform 2,048-token rerun. All four conditions have now generated all nine relation-only answers with a new shuffled condition-blind packet. This probe is scored separately and cannot substitute for complete numeric proof.

The 2,048-token relation-only blind grading is now complete (`qwen/.runtime/qwen35_external_teacher_20260925/scored-near-relation-2048/`). All 20 held-out-target answers (five IDs × four conditions) naturally stopped, while two H01 retention answers reached the cap. The stringent conjunction of a true useful relation, necessary branch, and decisive justification was **0/9 in every condition**. On held-out targets, one H04 response from 32-original stated the correct `AT²=BT·CT` relation and branch but did not derive it. The 36-multi arm, despite its complete H04 integrated answer, did not give a justified relation in this short prompt. One base H13 retention answer contained a true intermediate trigonometric relation but ended in a contradictory formula. The 180-word/no-numeric instruction was often violated; this diagnostic is strongly prompt-format-sensitive and does not negate the valid longer integrated H04 solution. Two independent blind reviewers caught an equivalence missed in the first H04 short-answer grade; the original, second, and adjudicated grades plus reason were all preserved before the condition mapping was opened.

The frozen second-seed nine-job pass has started. Its untouched-base condition completed 9/9 with natural `stop` on every answer (maximum 14,023 completion tokens; cap 32,768). Its job hash is `589f51a07dd4c77e8e6f2e8b4a713849c3267db95c4efb35500426ce2f85d679`; the 32-original adapter pass follows with identical prompts, seeds, and decoding parameters. These are repeats of the same numerical instances with new sampling seeds, not independent training-seed replications.

## Second-seed blind near-transfer result

All four conditions completed the same nine second-seed jobs; all 36 answers ended with natural `stop` below the 32,768-token cap. The 36 answers were shuffled and graded without condition labels. The six grade-file hashes and packet hash were frozen in `qwen/.runtime/qwen35_external_teacher_20260925/blind-near-transfer-repeat1/primary-grade-freeze.json` before the condition mapping was opened. Independent blind second reviews resolved the borderline H04 factor-cancellation and H08 generic-isosceles cases; the scores are in `qwen/.runtime/qwen35_external_teacher_20260925/scored-near-transfer-repeat1/`.

| Condition | Second-seed H03/H04/H14 complete | H08 | H15 | Four retention controls complete | Both seeds: five held-out jobs complete | Both seeds: retention complete |
|---|---:|---:|---:|---:|---:|---:|
| Base | 0/3 | 0/1 | 0/1 | 1/4 | 0/10 | 2/8 |
| 32-original | 0/3 | 0/1 | 0/1 | 0/4 | 0/10 | 1/8 |
| 36-multi | 0/3 | 0/1 | 0/1 | 1/4 | 1/10 | 2/8 |
| 36-repeat | 1/3 (H04) | 0/1 | 0/1 | 2/4 | 1/10 | 3/8 |

The H04 complete answer moved from `36-multi` on the first sample to the matched exact-repeat control on the second. Both have 1/2 H04 complete and 1/10 held-out complete over the two decoding seeds; neither meets the frozen 2/3 projection-ID threshold. The second-seed base and both other adapters often returned the correct H04 value and relation, but their proofs omitted or incorrectly justified the cancellation of the factor `AM²−(BC/2)²`. Acuteness mathematically excludes the zero case, yet those answers did not show that implication. H03/H08/H15 remain 0/2 complete in every condition. H14 sometimes had the exact value and right-angle relation but no valid derivation of the constructed projection. These are same model checkpoints and same numerical prompts under different generation seeds, so the two samples are not independent training or configuration replications.

The observed change between the two 36-row arms is compatible with decoding variation and does not establish an advantage from adding numerical variants. Retention is also low: the base solves only 2/8 paired same-configuration controls, while `32-original` solves 1/8. No adapter has yet met the external-teacher positive-control criterion. The predeclared next checks are all three projection-ID leave-one-out adapters, then the separately frozen fresh2 38-row data-form comparison and fresh3 six-source-variant comparison.

## Projection-ID leave-one-out, first decoding sample

Each of the three independent 36-row adapters omits one of H03/H04/H14 while retaining the other two projection-family sources. Each generated its permitted held-out target and all four retention controls on the frozen fresh1 jobs. All 15 answers ended naturally under the same 32,768-token cap. A shuffled condition-blind packet was graded before its mapping was opened; the packet and grade SHA-256 values are in `qwen/.runtime/qwen35_external_teacher_20260925/blind-loo/grade-freeze.json`, and the joined records in `qwen/.runtime/qwen35_external_teacher_20260925/scored-loo/`.

| Omitted target | Complete on omitted ID | Paired untouched base | Retention complete | Paired untouched base retention |
|---|---:|---:|---:|---:|
| H03 | 0/1 | 0/1 | 1/4 | 1/4 |
| H04 | 1/1 | 0/1 | 1/4 | 1/4 |
| H14 | 0/1 | 0/1 | 1/4 | 1/4 |

The H04 answer contains a self-contained coordinate proof of the projection parameter and the identity `AT²=BT·TC`, handles the `T,B,C` order, and obtains `sqrt(69)/2`. The H03 answer ends at `OH/2` after a sign error in its bisector-circle calculation; H14 guesses a wrong reflection relation and does not solve the area. H04 has also appeared as a complete answer under different arms on the earlier two decoding seeds, so this single LOO success cannot establish a stable causal effect of omitting H04 or transfer across the projection cluster. The three targets share a lemma family and are not independent theorem discoveries.

The three fresh2 38-row data-form adapters (`direct-multi`, matched `repeat`, and `balanced-qa`) have now each trained from the original base for 38 updates at LR 1e-5. Each passed 400/400 changed-tensor and reload checks, with about 21.17 GiB peak allocated GPU memory. Their still-blind nine-job fresh2 evaluation has begun with the untouched base. No fresh2 answer has been scored at the time of this entry.

## Fresh2 data-form comparison, blind result

All four conditions completed all nine fresh2 jobs with the identical frozen job hash `9947444ede2b19d1122f1a7be0e830299cc12b91c90edd24e94f8cca17670e71`. All 36 generations ended naturally, with a maximum of 12,352 completion tokens under the 32,768-token cap. The packet and four final grade-file hashes were frozen in `qwen/.runtime/qwen35_external_teacher_20260925/blind-fresh2/grade-freeze.json` before the condition mapping was opened. Independent blind reviewers adjudicated H04, H14, H01, and H02 borderlines. The joined grades and item pairs are in `qwen/.runtime/qwen35_external_teacher_20260925/scored-fresh2/`.

| Condition | Complete on five held-out IDs | Projection H03/H04/H14 | H08 | H15 | Four retention controls |
|---|---:|---:|---:|---:|---:|
| Base | 1/5 | 1/3 (H04) | 0/1 | 0/1 | 1/4 |
| 38 direct-multi | 0/5 | 0/3 | 0/1 | 0/1 | 0/4 |
| 38 repeat | 0/5 | 0/3 | 0/1 | 0/1 | 1/4 |
| 38 balanced-QA | 0/5 | 0/3 | 0/1 | 0/1 | 1/4 |

No arm proved H03 or H14's hidden construction-to-projection step, or completed H08/H15. The base H04 response gave a complete alternative coordinate proof. The repeat and balanced-QA H04 responses obtained the right relation and value but failed strict proof review, respectively for unjustified cancellation and inconsistent midpoint coordinates/skipped decisive algebra. The 38-row treatments did not produce a complete held-out solution even on this development set. Across the five held-out items, base had (exact, relation, proof, use) = (1, 2, 1, 1), direct-multi (1, 1, 0, 0), repeat (2, 3, 1, 2), and balanced-QA (2, 2, 0, 2). These component signals are exploratory and do not compensate for missing complete proofs. One base H02 retention answer reaches the exact answer through a later correct coordinate derivation but never explicitly retracts an earlier false relation; strict grading marks proof false. A permissive self-correction rule would increase only base retention to 2/4.

The fresh3 six-source numeric-variant and matched-repeat adapters have independently completed 50 updates from base; both passed 400/400 reload checks. Fresh3 untouched-base evaluation is running on the separately frozen nine-job set. The predeclared run order keeps fresh3 ahead of the result-informed structural bridge experiment.
