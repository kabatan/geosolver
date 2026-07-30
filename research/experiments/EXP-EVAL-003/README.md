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
