# Decision

`D0_REJECT_SAFE_ACTIVE_NO_RECALL_SIGNAL_AFTER_REPAIR_A`

Both the initial persistent-dual single-row projection and the one permitted
mathematical repair were active and safe, but neither added a generated
portfolio solve.  The frozen Repair-A result is `0` gains, `0` losses, `0`
false accepts over 108 positive/negative/near-miss cases, with exact callback
work, exact 75% baseline-lane preservation, and 12/12 metamorphic checks.

The non-Euclidean persistent dual is a valid causal reopen relative to the
old Euclidean and block-Kaczmarz implementations, but this implementation has
no recall signal to justify a real adapter or D1.  No benchmark, truth,
target, HP/CAS, validation, or sealed data was used.
