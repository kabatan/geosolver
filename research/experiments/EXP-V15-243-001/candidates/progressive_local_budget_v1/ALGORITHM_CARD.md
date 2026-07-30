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
