# Current-campaign connector decision

**HOLD_MISSING_CURRENT_MAP_CHECKPOINT_SEAM — connector not built.**

The D0 AMS mechanism remains valid generated evidence, but the current
archive champion/progressive search does not expose a resumable local state.
Both progressive bindings declare `current_checkpoint_support = false` and
charged original-start reexecution.  The underlying deep binding rejects any
supplied checkpoint, runs the incumbent solve inside a disposable fork child,
and returns `checkpoint=None` / `checkpoint_resumable=False`.  Its surviving
parent telemetry is endpoint/status/counter data, not current/best, partial J,
Broyden, trust/LM, pending-transition, acceptance-window, refresh, or RNG
state.

The parity-passed Wave-10 checkpoint kernel does contain the complete state
needed by AMS, but it checkpoints mature parent `e9c9bd7f...`.  The current
champion search map applies accepted-semantic-invalid retention followed by a
conditional strict near-root restart (`d2904af6...`; transformed source
`036f48e5...`).  Calling Wave-10 as though it were that map would silently
replace the incumbent numerical algorithm.  Porting those transformations
and redoing every-cut parity would be a new checkpoint kernel and repair
chain, not a thin connector.

The stopped stateful-successive-halving lineage does not reopen the seam.  It
uses its own `LaneCheckpoint` and numerical kernel rather than Wave-10
`CheckpointState`, and its best-half mechanism is explicitly prohibited for
this candidate.  Reusing its full-worker/lifecycle stack would also couple AMS
to a stopped lineage and to the historical containment surface currently
being repaired elsewhere.

The archive exact-outer `CONFIRM_ALL_AUTHORITIES` and zero-dimensional source
authority are present, but authority after endpoint emission cannot create the
missing local trajectory state.  No connector, worker, BASE lifecycle hook,
serialization layer, common scheduler, or emission route was created.

## Reopen gate

Reconsider only after an independently motivated common-private fixed BASE
naturally exposes the current transformed map as an in-process checkpoint,
including current/best observations, residual/guard state, partial/fresh J,
direct Broyden model, trust radius, LM damping, pending transition,
nonmonotone/acceptance windows, refresh state, exact callback ledger, and RNG.
It must pass uninterrupted-versus-every-callback-cut parity across both the
accepted-invalid and near-root-restart paths, reject cross-source resume, and
preserve deadline/callback accounting.  The fixed search binding must then
advertise true checkpoint support without original-start reexecution and own
all process lifecycle.  Only after that may a <=25% AMS side emit fresh-
replayed endpoints through exact_outer `CONFIRM_ALL_AUTHORITIES`, with the
zero-dimensional route remaining object-identical.

This audit used static source/hash inspection and a source-only seam probe.
No formal CPU 0–6, real case execution, scorer, truth, validation/sealed input,
source solve, or target emission was used.
