# Shared-search dual-admission re-audit: PRE-CODE STOP

Date: 2026-07-31 (Asia/Tokyo)

## Decision

Do not create a candidate from the frozen `shared_search_dual_admission` arm.
The current archive-progressive-exact stack already contains the permitted
target-free multi-configuration admission mechanism, while the only additional
frozen legacy lane violates the requested semantic and budget contracts.

The historical source-only aggregate `control 48 / champion 52 / oracle union
53` is proposal motivation only. It came from separate full-wall arms and is
not evidence that a same-wall portfolio improves recall.

## Whole-repository findings

### Frozen legacy dual lane is not composable

The frozen dual worker reuses one raw search stream, but its side lane calls
the legacy finalist `_fresh_replay_candidates`. That path performs 80-digit
provisional-target replay and target-cluster admission before HP. The
independent terminal decision records `NO_GO`: preserved ordering provenance
used diagnostic/provisional targets and therefore fails the absolute
no-target-during-ordering gate.

Its only authorized schedule is also fixed at 30 seconds. After the shared
search and selection, champion HP receives 3.5 seconds and legacy side HP
receives 3.0 seconds plus 0.5 seconds of target replay. Thus the competing
post-search lanes are effectively 50% baseline / 50% side, not the required
baseline at least 75% and immature side at most 25%. The schedule rejects any
other total rather than scaling.

Repairing both defects requires a newly specified target-free ordering,
precheck, scheduler, and audit. The frozen terminal authority explicitly calls
that a different algorithm candidate. It cannot be produced by a thin shim
while preserving existing search, HP, and replay.

### Current stack already has the lawful mechanism

The current champion-v0 path performs a target-free residual/guard/hard scan,
then builds one lossless configuration-maximin reservoir from the raw endpoint
stream. It assigns every unknown-target discovery an independent primary:

- no selection-time target evaluation;
- no pre-descriptor irreversible deduplication;
- equal endpoint bytes remain distinct discovery records;
- same-target candidates are not removed;
- an authority for one configuration does not suppress another configuration;
- deferred rows remain explicit and are breadth-first aged;
- `cross_cluster_candidate_suppression` is false.

`archive_progressive_hybrid_exact_outer_v1` uses this same champion BASE. Its
positive-dimensional HP callable is captured exactly once by global
`CONFIRM_ALL_AUTHORITIES`, so every ordinary emission remains proposal-only
until exact source/guard/branch replay. Its zero-dimensional path retains the
existing source-exact champion-v2 authority.

Adding a second copy of this reservoir would only duplicate an already active
mechanism. Adding the frozen legacy selector would reintroduce prohibited
target ordering. With no side lane, the effective baseline share remains 100%.

## Read-only/unit verification

All checks used CPU 31. No `--execute`, scorer, truth, real-case result,
validation/sealed input, HP child, or formal CPU was used.

- Frozen endpoint-reservoir unit suite: 14 passed. It includes no-record-loss,
  same-target/equal-byte retention, configuration-maximin ordering, bounded
  aging without deletion, anonymous target-unavailable admission, and a target
  evaluator that must never be called.
- Current progressive + exact composition suite: 7 passed. It confirms one
  shared historical BASE, progressive search activation, unchanged PoC HP
  capture, exact fail-closed authority, zero-dimensional identity, and the
  existing search baseline/insurance quotas.
- The previously frozen source-only positive PLAN for the current composition
  reports `progressive_adaptive_hybrid_64_600`,
  `CONFIRM_ALL_AUTHORITIES`, capture count 1, and ordinary authority bypass
  false. The zero-dimensional PLAN reports `source_exact_zero_dimensional` and
  unchanged authority logic.

## Reopen gate

Reopen only after a new, separately audited artifact-only mechanism supplies a
target-free legacy ordering that is not identical to the current lossless
configuration reservoir, demonstrates additional configuration admission on
the same synthetic stream, preserves at least 75% baseline budget, caps the
side lane at 25%, and leaves search/HP/replay/exact authority unchanged.

Do not use the historical 48/52/53 aggregate, case identities, target values,
or prior outcomes to construct that ordering.
