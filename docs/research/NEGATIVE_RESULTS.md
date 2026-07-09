# Negative-Result Ledger

The machine-readable ledger is
[`research/negative-results/ledger.json`](../../research/negative-results/ledger.json).

Initial entries are explicitly marked `prior_unreproduced`: they motivate
counterexamples but are not accepted truth in the clean repository. An entry
moves to `reproduced` only after its problem generator, run manifest, compact
result and checksum are recorded here. A locked-validation result is never
silently converted into a tuning case.

The ledger currently prevents five recurring mistakes:

1. selecting starts only by screening residual;
2. hard suppression of nearby basins;
3. treating naive lifting/homotopy as universal improvements;
4. confusing a barrier-near point with strict-guard validity; and
5. using dynamic expression evaluation as a production numerical kernel.

Rejected production code is deleted, while the card, counterexample generator,
compact result, decision and artifact hashes remain.
