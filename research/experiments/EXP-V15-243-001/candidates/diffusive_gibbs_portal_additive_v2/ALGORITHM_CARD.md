# Diffusive-Gibbs additive tail — Repair A

## Trigger

The replacement-based D1 was semantically clean but non-monotone across three
aggregate seeds: control→candidate `15→16`, `15→16`, `16→15`, with
false/extra/crash zero.  No case-level result was disclosed.  Repair A changes
the connection mechanism rather than tuning a quota.

## Mechanism

The current adaptive baseline runs first, once, with its original literal
prefix, scheduler, callback ledger and deadline.  Its outcome is retained.
Only when both callback and wall surplus remain does a fork-isolated DiGS
scout run over the immutable prefix plus retained reservoir endpoints.

Admissible proposals must be finite, dimension-correct, inside explicit source
bounds, and different bytewise from retained baseline endpoints.  They form a
separate four-slot tail cohort required by the existing scheduler contract:
ordinal zero uses the frozen counter-Cauchy insurance source and the remaining
slots use the DiGS tail source.  The current adaptive local solver processes
this cohort using only the still-unused aggregate callback/deadline budget.

The returned endpoints and lane-callback records are:

`baseline prefix || additive tail`

Baseline endpoints are never replaced, reordered, filtered, or discarded.
Baseline status/counters remain and tail telemetry is namespaced.  The
unchanged search worker performs source replay over the union; HP, reservoir
composition, descriptor deduplication and final canonical authority remain the
common-control implementation.  With no usable surplus the exact baseline
outcome object is returned without reconstructing or annotating it.

## Connection evidence

Two source-only runs used no scorer, truth, correctness result, validation or
sealed data.  One activated after retaining 32 baseline endpoints and 48
baseline lane records, spent 28 surplus scout callbacks, generated two
admissible proposals, and appended four tail endpoints/six tail lane records.
The other had no safe surplus and returned the unannotated baseline path.  Both
kept source bytes unchanged and completed inside the worker deadline.

Decision: `PASS_REPAIR_A_CONNECTION_SMOKE_ONLY`.  A fresh benchmark-owner D1
is required; prior replacement-based D1 numbers are not evidence for Repair A.

## Frozen closure

- Search adapter: `856602efd5d1ac96464fa1a83dfad0f8f936b8dcd16ba5a95d0fad67371c22eb`
- Search worker: `b5f7fb6c431346458a06a0893789e5f9012e3178b54ac57efeead423cea4de7d`
- Full wrapper: `e2a64742bd2c10f3feb983ed2d7a3ca068d5505a738e3124ea6b56f2229c2135`
- Entrypoint: `b8e5c81ee4c690399144a126491d23498e8b911f142f77dc6f16e1775480edd0`

No shared scheduler/framework file was changed.
