# Exact-descriptor species racing — Repair A

Status: `GENERATED_REPAIR_A_PASS; LOSS_ZERO; COMMON_ARM_UNCHANGED`.

- Policy SHA-256: `8a22ef789fb035c7acb9c3c65f16aa2533fdc86c2c428ef8e28be42a281a60a1`.
- Runner SHA-256: `b36a50651c72c8e62d22f37b4c51a87aeaa3e235f855c10b5651f1c44cba7814`.
- Aggregate SHA-256: `c1ebf4f1b238af03dbd4600dde9507b15c3ba93a74c25d72e72111ba009393c5`.

## Causal repair

D0 reallocated a generic side budget and gained recall, but lost 13 control
descriptors in seven cases. Repair A does not retune the estimator. It changes
the only borrowable work item:

1. Preserve 96 ordinary actions and 24 counter-Cauchy insurance actions
   exactly, giving a nonborrowable 75% prefix.
2. Preserve two independent shared scout blocks for HP and branch.
3. Borrow only an unstarted deep handoff explicitly typed as incapable of
   generating a novel descriptor, and only when its descriptor already passed
   authority in at least two independent blocks.
4. Require the selected route to have Good--Turing unseen mass at least 0.5
   and bias-corrected Chao2 unseen species at least 1.
5. Charge the replacement block exactly the handoff work and publish only the
   union of its proposals with the retained control descriptor union.

The policy never suppresses output or claims completeness. Runtime status is
always `UNKNOWN`. Descriptor values, target count, case/family identity,
truth, and prior outcomes are not candidate inputs.

## Generated result

The 400-case equal-work panel repeats the three D0 mechanisms and adds
delayed-rare and false-saturation adversaries. Every family crosses target
cardinalities `1/2/5/10` with 20 replicates.

- Complete sets: `180 -> 229`.
- Descriptor gain/loss: `+294/-0`; strict gains in 112 cases and 4/5 families.
- Activation: 127 cases, 246 borrowed handoffs.
- False/extra, control suppression, work mismatch: all zero.
- Metamorphic agreement: `800/800`.
- False-saturation: borrow 0, gain/loss 0, so correlation does not manufacture
  a high-unseen trigger.
- Delayed-rare: 120 descriptor gains and zero loss.

No formal truth, scorer, development case score, validation, sealed, or
holdout input was read. `arm.json` and the exact common control are unchanged.

## Repair B boundary

Repair B is closed because Repair A has generated loss zero. Reopen it only if
benchmark-owner aggregate evidence shows a recurring loss or a failure of
`control_union <= candidate_union`. Such a failure means the real adapter did
not establish the typed redundancy contract or did not retain the exact
control snapshot. The only admissible Repair B is snapshot-first post-control
union or a stronger proof that the handoff cannot generate novelty; changing
unseen thresholds, lane fractions, or route order is not a reopen condition.
