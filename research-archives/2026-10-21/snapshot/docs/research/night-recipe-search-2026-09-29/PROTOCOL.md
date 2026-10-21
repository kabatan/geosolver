# Overnight numeric-experience recipe search

Authorized: execute the 13-hour plan. Start 2026-09-28 17:30:45 UTC;
hard deadline 2026-09-29 06:30:45 UTC (15:30:45 JST). Stop starting
additional experimental bundles at 05:00:45 UTC, reserving 90 minutes for audit.

Primary question: can numeric answers alone, without teaching the target proof,
improve correct, validly reasoned solutions to different geometry problems?
Same-configuration fit is diagnostic only. This is exploratory recipe search,
not a confirmatory significance claim or a test of all possible learning methods.

Frozen training families: H01,H04,H07,H13,H15,DA01,DA05. S contains the original
56 rows. D contains those rows plus 56 new non-similar shapes per family (448).
Keep each family's eight original baseline lengths, eight shapes per baseline.
Baseline AB for H07/H15, BC otherwise. Additional 16 shapes per family form a
112-row diagnostic holdout. Exclude every existing numeric-case shape signature.
Labels are measured from the original point/line/circle construction, without
using target theorem identities. Independently reconstruct at high precision.
All shuffles are within family, preserve prompts/order/target multiset, and have
no unchanged target. D is a shape-diversity intervention, not more update steps.

Arms: Base, S128, X128, S512, X512, D512, DX512; X/DX are shuffled controls.
Training seed 2026093001; continuation 32 -> 128 -> 512 with optimizer state and
prefix order verified. Fixed model revision c202236235762e1c871ad0ccb60c8ee5ba337b9a,
LoRA r8/alpha16/dropout0, lr5e-6, accumulation4, bf16, the existing ten target
modules, assistant numeric answer plus EOS CE, no thinking. No checkpoint search.

Main screen: H02,H03,H08,H12,DA03,DA06,DA07,DA11,DA15,DB01,DB08,DB16, one sample
per family for every arm. A second sample for Base/S128/X128 reproduces the
24-output comparison. Common ordering: all first samples, then all second
samples. Identical batching (4) and per-job sampling seeds in every arm.
Also run four retention questions and greedy diagnostics (original56, holdout112).
Never pool historical outputs with the new outputs.

Generation bounds: 32768/40960, then 81920/98304, then 131072/147456
(completion/context). If any arm hits a cap, regenerate that same ordered job
subset for all arms in the comparison at the next bound. A regeneration is a
fresh sample, not a continuation; no best-of selection. Persist every stage.
Incomplete comparisons are censored, not negative evidence.

Numeric correctness: committed final answer, abs error <=1e-4 or relative error
<=1e-5. Primary success additionally requires valid reasoning. Review numeric
successes with randomized condition-hidden IDs, with valid/invalid/unclear and
an explanation; unclear is not primary success. Correct applicable named or
specialized geometric properties are allowed in numeric solutions. Guesses,
circular assumptions, and disavowed false derivations do not qualify. Preserve
a lenient sensitivity score separately. Review is by the executing assistant,
not claimed to be an independent human review.

Branch A gate on the common12: valid successes >=Base+2, strictly more than
matched shuffle, improvements in >=2 families, numeric successes >=Base, retention
>=3/4. Rank by valid successes, advantage over shuffle, numeric successes, fewer
updates. This is an exploratory gate, not a significance threshold.
If eligible, retrain winner and shuffle with seed2026093002; evaluate Base and
both new adapters on 12 old problems with new inference seeds plus six frozen
new shapes (H02/DA15/DB08, two each). These three families were chosen from prior
improvements, so this is targeted diagnostic confirmation. If all six cannot be
validated within preparation's two hours, omit the whole fresh-six set.

If no completed arm qualifies, Branch B tests D512 with answers rounded to six
significant digits and a matching six-digit answer instruction, plus its shuffle.
All other settings stay fixed. Verify rounding error is within the scorer's
tolerance. This is a representation/instruction package, not an isolated loss
change. Compare common12 against Base/D512/DX512. No additional recipe fishing.
If the main comparison is incomplete, prioritize completing it instead of B.

Time budget: preparation <=2h; train/diagnostics ~1h; main/evaluation/audit ~5h;
branch until hour11.5; final audit/report by hour13. Re-estimate from actual speed.
Use the existing shared exclusive GPU lock and verify any desktop compute PID.
No reset, driver change, or termination of unrelated processes. One identical
retry for transient errors only; log both attempts. Deadline termination affects
only the process group created for this campaign. Preserve partial outputs.

Artifacts: frozen prompts/keys/data/witnesses/hashes/configs, original raw outputs,
adapter and optimizer receipts, numeric scores, blind reasoning review, final
comparison and an explicit recommendation (including a negative conclusion if
warranted). Existing files and experiments are not overwritten.
