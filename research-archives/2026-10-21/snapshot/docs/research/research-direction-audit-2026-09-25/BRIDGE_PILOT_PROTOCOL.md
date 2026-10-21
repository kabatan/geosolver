# Bounded H14 bridge-format diagnostic

Frozen before the new training and outputs, 2026-09-25. This is a new,
deliberately reduced exploratory pilot, not execution or completion of the
earlier seven-condition/ten-job bridge protocol. Existing protocols stay intact.

## Decision and scope

Compare the previously audited, untrained rotation-3 treatment/control datasets.
Both contain the same 32 common rows and six H03/H04 rows, with H14 excluded.
Treatment separates relation identification, proof, and a standalone complete
solution; control uses three paraphrased complete solutions. Both have 38 rows,
34 source IDs, one epoch at LR 1e-5, rank 8/alpha 16, seed 2026092431, from the
same original Qwen3.5-9B weights. Use the existing trainer unchanged. Merged
answer tokens differ by 0.364%; added-only tokens differ by 5.32%. This is not
a perfectly equal-dose experiment.

H14 was chosen using existing diagnostics because it fails construction-to-foot
proof while downstream use succeeds with a supplied foot premise. H03 has an
additional downstream circle-center failure. This selection is result-informed.
H14's construction has an inversion argument absent from H03/H04, so even a
negative result cannot isolate the SFT objective from missing prior capability.

## Evaluation fixed in advance

Use only H14 from the existing fresh4 first/second-seed job files: two numerical
instances times two decoding seeds, four outputs per arm, eight total. Keep
English prompts unchanged. Non-Thinking, temperature 1, top-p .95, top-k 20,
presence penalty 1.5, output cap 32768/context 45056, one sample per job.
These are already-used development configurations, not confirmatory data.
There is one independent target construction and one training seed per arm.

Run both seeds regardless of first-seed results. No adaptive checkpoint or prompt
selection. The original all-rotation conditional second-pass rule does not apply
to this separately scoped pilot. No baseline superiority or retention claim is
possible from this two-arm diagnostic. No optional arms are launched from its
result during this audit.

After all outputs complete, create a shuffled condition-blind packet. Grade the
existing construction-proof, exact-value, relation, branch, and use criteria;
complete success requires a valid full derivation from the original construction.
Freeze grades before revealing arm identities. A positive differential on only
one output is a candidate, not stable transfer; any positive result needs fresh
construction and independent training replication. Zero valid construction proofs
in both arms is a stop signal for scaling this particular short-teacher recipe.

If a completion is truncated, label it incomplete and do not infer inability from
that item; a longer-budget follow-up would be a distinct diagnostic. Existing
non-Thinking H14 outputs naturally ended far below this cap. Training and
generation receipts, hashes and actual elapsed time are retained. Anticipated
generation time 15–30 minutes is a rough estimate from earlier runs, not a promise.

The broader research asks for model-generated mathematical knowledge selected by
verification without external target solutions. This experiment deliberately
uses external proofs as an easier feasibility diagnostic, not evidence for that
broader hypothesis.
