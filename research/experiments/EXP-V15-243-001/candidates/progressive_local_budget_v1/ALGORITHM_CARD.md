# Progressive local budget v1

## Hypothesis

Several development misses completed only one or two starts because one local
attempt consumed nearly the full search window.  Giving every original-prefix
start a bounded first tranche before any promotion should expose more basins,
while deeper work can be concentrated using source-only progress evidence.

## Candidate delta

- profiles: `64 -> 192 -> 600` and `96 -> 300 -> 600` callbacks;
- every start receives the first tranche in original ordinal order while time
  and callback budgets permit;
- attempt wall cap: `max(0.5, min(4, 2 * remaining / unserved))` seconds;
- promotion uses only source semantic validity, residual/guard progress,
  optional model ratio/rank stability, charged callbacks, and measured wall;
- the every-fourth counter-Cauchy lane retains at least 25% of service slots;
- no lane is permanently suppressed and the proposal prefix is immutable.

The frozen champion local kernel and fail-closed process isolation are reused.
Because that kernel exposes no resumable checkpoint, deeper services currently
re-execute a charged prefix from the original start.  This is deliberately
visible in telemetry and is the main performance risk of the prototype.

## Information and safety boundary

No case ID, family, truth, answer, target count, validation split, or sealed
split is an input.  Source equations, guards, bounds, evaluator, callback
ledger, HP/exactification and canonical verification are unchanged.

## Stop rule

Reject a profile if minimum-service activation fails, if it creates any source
safety regression, or if prefix reexecution overhead dominates without a
starts-serviced or safe-endpoint gain on an outcome-blind development screen.

## Full-v15 S1 entrypoints

`arms/profile64/arm.json` and `arms/profile96/arm.json` bind separate full-v15
entrypoints.  Each hash-loads the frozen finalist numeric worker and replaces
only its discovery seam.  Source replay, HP/restoration, canonical authority,
exact descriptor deduplication, and the final result schema remain frozen.

## Truth-free metamorphic S0

`metamorphic_s0.py` generates a 32-start narrow-basin search without repository
case, family, answer, validation, or sealed inputs; its target is constructed
inside the harness.  For both profiles it checks all-start first service,
deepest-rung reachability, callback-ledger reconciliation, the counter-Cauchy
insurance floor, long-callback starvation, and re-promotion after a preempted
service returns usable endpoint evidence.
The all-start guarantee covers every regular/IID proposal, and the generated
ranking also checks that all three regular source streams retain a deep solve.

Variable permutation, residual permutation, and positive affine variable plus
common residual scaling must preserve the complete `(start, rung)` decision
trace.  The S0 also asserts fail-closed behavior for callback overcharge,
negative/zero charges, malformed endpoints, proposal-prefix mutation, and a
counter-Cauchy insurance mismatch.  The deterministic output is frozen in
`METAMORPHIC_S0_EVIDENCE.json`; it is mechanism evidence only, not an S1 recall
or speed result.
