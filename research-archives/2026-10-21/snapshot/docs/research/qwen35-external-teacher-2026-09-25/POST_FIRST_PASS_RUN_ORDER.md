# Run order fixed before second-seed and leave-one-out grading

This exploratory queue was recorded while the second-seed `32-original` generation was in progress, before any second-seed answer text was opened. Its purpose is to avoid running only a favorable item or arm.

1. Complete the frozen second-seed nine-job pass for base, `32-original`, `36-multi`, and `36-repeat`; blind-grade all 36 answers before joining conditions.
2. Evaluate all three already trained leave-one-projection-ID adapters, each on its permitted target plus all four retention controls, and blind-grade all 15 answers. The untouched-base first-pass answers are the paired reference. A repeated LOO sample, if warranted, must cover all three arms and their full five-job lists.
3. Regardless of the results in steps 1–2, train the already audited 38-row `direct-multi`, `repeat`, and `balanced-qa` files from the original base with the common frozen recipe. Evaluate all three and the untouched base on every one of the nine fresh2 jobs, then condition-blind grade. This is a data-form diagnostic, not a checkpoint-selection exercise.
4. If the independent audit of the newly prepared 50-row six-source numeric-variant teachers passes, train that candidate and its matched exact-v0 repeat control from base and evaluate both plus untouched base on all nine separately frozen fresh3 jobs. This comparison was added before second-seed/LOO/fresh2 answers were graded. Keep it exploratory and report the six source IDs, total tokens, and all outcomes.
5. Use the seven-job supplementary retention sentinel as a separate, result-informed diagnostic if GPU time allows after the transfer comparisons. Compare the same prompts and seeds for base, `32-original`, `36-multi`, and `36-repeat` on all seven jobs; report all outcomes without folding these items into held-out transfer counts.

The current external-teacher experiments are a positive control for the later self-generated study. They cannot establish that the model discovered a relation without external proof supervision. Preserve complete failures and component scores alongside any positive answers.

## Added after the first LOO grades (result-informed exploratory stage)

The LOO result was H03 0/1, H04 1/1, H14 0/1 with 1/4 retention in every arm. A GPT-5.6-Pro review noted that H04 explicitly supplies its projection foot, whereas H03/H14 require proving that a circle construction hides the projection. Accordingly, a new structural bridge comparison is added **after** the predeclared fresh2/fresh3 queue, subject to its teacher audit. It uses three omit-one-ID rotations and matched decomposed versus integrated-answer data from the same two permitted sibling IDs. Its primary transfer targets are H03/H14; H04 is a lower-bar formula-use probe. The frozen fresh4 target prompts predate LOO scoring; the ten-job evaluation assembly and bridge design are result-informed and exploratory. Protocol: `heldout-near-transfer/followup-bridge-eval/PROTOCOL.md`.
