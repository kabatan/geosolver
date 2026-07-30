# EXP-EVAL-003: deadline-isolated incremental continuation

Status: **S0_FORMAL_ARM_READY_AWAITING_ROOT_OWNED_SCREEN**.

EXP-EVAL-001's first full-worker wrapper was rejected by the formal owner after
one case exceeded the requested 30 second wall budget (`30.404s`).  This v2
closes that reopen gate at the outermost process boundary.  It deliberately
uses the frozen champion entrypoint directly instead of the timing-sensitive
optimized wrapper.

## Mechanism

For a requested `30s total / 20s search` run, the wrapper gives the frozen
champion `27s total / 18s search`.  The three-second deduction is made before
the champion dry/execute plan is frozen and is compatible with its integrated
selection, HP, and finalization reserves.

If the initial run produced an accepted `search.json`, continuation runs in a
separate process group.  Its absolute kill boundary is `outer deadline -
1.5s`; the whole descendant tree is terminated at that boundary.  The initial
frozen result remains the default.  A child result is promoted only when:

1. its result and truth-free incremental telemetry were atomically completed;
2. the v15 schema, source SHA, completion flag, and all safety fields match the
   frozen initial result;
3. the incremental overlay reports a complete source-bound prefix extension;
   and
4. at least one second of the outer budget remains.

A child killed during post-result cleanup may therefore be promoted, but an
incomplete, corrupt, authority-mismatched, late, or absent artifact cannot be.
Missing `search.json` is a normal fail-closed path.  Canonical replay, HP,
exactification, and the result schema are unchanged.

The continuation child installs the EXP-EVAL-001 append-aware reservoir
overlay.  Old endpoint observations are reused only after the source SHA,
immutable search plan, checkpoint content digest, and exact endpoint prefix
match.  Backlog, previously unobserved endpoints, and the appended suffix are
still semantically replayed; no answer or exact descriptor is cached.

## Common-control integration audit

The frozen entrypoint is the exact selected common-control worker, not the
lower `finalist_numeric_worker_v15` alone:

```text
/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/
EXP-V15-243-001/repro_20260722/workers/champion_v2_poc_preloaded.py
SHA-256 e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301
```

The path is hash-checked before import.  Its loaded composition is
`precision_runtime_preload -> champion_v2_poc wrapper -> champion_v2
zero-dimensional authority -> POC champion_v1 wrapper/approved HP bridge ->
champion_v1 -> champion_v0 -> finalist_numeric_worker_v15`.  Thus both the
champion-v2 exact-source layer and the champion-v1/PointOnCircle periodic
semantic layer remain active.  The frozen selection card names this same path
as the common control.

Two direct-entrypoint differentials were run without truth or scoring:

- On a zero-dimensional source, wrapper and direct-control plans differed only
  in `output`.  Results differed only in wall time and the numeric replay
  artifact hash.  A second direct-control invocation changed those same two
  fields, confirming that the replay hash binds volatile backend process
  telemetry.  Exact descriptors, champion-v2 authority, POC/champion-v1 safety
  fields, status, schema, and every other result field were equal.
- On a positive-dimensional `14s/2s` wrapper fail-close (the exact control
  received its corresponding `11s/2s` internal budget), plans again differed
  only in `output`.  Results differed only in wall time: both were accepted by
  the common runner predicate, returned the same empty exact set, and retained
  identical `SEARCH_DEADLINE_REACHED` / search-timeout / safety semantics.

Consequently no control-stack rebind is required before screening.  The arm
changes custody only after the exact common-control initial phase completes.

## S0 evidence

All raw artifacts are outside Git under
`/home/kabatan/work/solver-artifacts/exp-eval-003`.

- Final `30/20`, seed 0, `256 x 600` smoke on source `9de1f105...` was accepted
  by the frozen dataset-runner predicate.  It finished in `26.6131s`, leaving
  `3.3869s`; continuation completed and was promoted.  Of 71 covered
  endpoints, 47 verified records were reused and 24 were semantically
  replayed.
- The known missing-search source `63fb3e07...` was also accepted.  It finished
  in `23.1490s`; no continuation was started and the initial result was
  retained without a crash.
- Truth-free slow-child probes show both no-start behavior when the reserve is
  already too small and process-tree termination at the reserved boundary.
  The unit suite is `3 passed`; Ruff and byte compilation pass.
- EXP-EVAL-001 separately established 2,175 bit-identical generated candidate
  comparisons and a 66.7% semantic-replay reduction.  This wrapper changes
  only custody and timing around that mechanism.

No scorer, problem truth, validation/sealed partition, formal screen, or heavy
HP benchmark was read or run.  Formal S1/S2 measurement remains exclusively
owned by the root benchmark process.

## Reproduction notes

Use the frozen Python environment, pin the outer process to the declared CPU,
and preserve the champion's dry-run `PLAN.json` SHA when adding `--execute`.
The public arm entrypoint is `worker.py`; its arguments are the common worker
contract.  The sidecar `EXP-EVAL-003-TELEMETRY.json` records internal budgets,
child disposition, activation, replay counts, and authority invariants.
