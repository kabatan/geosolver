# Research metric harness

This package is a standard-library-only safety boundary between solver output
and research claims. It does not inspect geometry names or tune solver policy.

## Truth and answer matching

`parse_case_input` and `parse_run_input` reject unknown fields, binary floating
point thresholds and incomplete evidence flags. Gold entries are distinct
target values, not configurations. Consequently, two validated configurations
that produce the same target cover one Gold entry and the second is recorded as
a duplicate witness.

A case selects exactly one matching rule:

- `certified_interval`: both Gold and reported target intervals must be
  certified; a report must overlap exactly one branch-compatible Gold interval.
- `declared_tolerance`: the manifest supplies the only permitted tolerance. A
  report's midpoint must be within it and its interval cannot be wider than two
  tolerances. There is no implementation epsilon.

Every accepted answer also needs canonical configuration, guard and boundary
validation. Exact answers additionally need an independent target-identity
certificate. Level-specific false counts are disjoint; branch, boundary, guard
and ambiguity counts are diagnostic subsets and must not be added again.

## Completion statistics

`aggregate_metrics` reports raw run-level `P_full` plus a family-clustered
one-sided 95% lower bound overall, for all S1-S8 slices, and separately for
bounded and adaptive-unbounded cases. Exact denominators contain only cases
predeclared exact-eligible. Empty mandatory slices remain visible with `None`
rates instead of disappearing.

`stability_27_of_30` fails closed on missing or unexpected seeds. Supply
`expected_case_families` to expose cases for which no run was produced at all.
`prefix_monotonicity` pairs by case and seed, checks both validated and exact
target-set inclusion, and measures how many 180-second misses become fully
validated at 420 seconds.

Bootstrap plans persist every resampled family index and a canonical SHA-256
checksum. The stored indices, not regeneration from a seed, are the replay
record. Families receive equal weight even when they contain different numbers
of cases or seeds.

## Partition gate

`PartitionRegistry.access` permits:

| Access mode | Readable state |
| --- | --- |
| development | D1/D2/FUZZ development sets and explicitly burned sets |
| validation evaluation | active V1/X1 locked sets |
| blind evaluation | active F1/P1 blind sets |

Opening a locked or blind failure uses `burn_and_replace`. It atomically marks
the original family set burned (and therefore development-readable) only after
a family-disjoint replacement has passed all checks. The immutable burn record
retains both family lists and the reason.

## Miss Analyzer

`research.harness.miss_analyzer` combines typed `CaseInput`, `RunInput` and
`RunEvaluation` with optional canonical solver evidence/checkpoint events and
audited causal facts. It reports the earliest evidenced F0-F18 checkpoint or a
typed `unknown`; absent logs never become no-capture, fairness or completeness
evidence. See [the full contract](../../docs/research/MISS_ANALYZER.md).

## Formal performance-run exclusion

Wall-clock experiments must be launched through
`python -m research.harness.exclusive_run`. The wrapper takes one advisory host
lease shared across worktrees, streams a heartbeat, and writes an atomic JSON
audit containing the command, child PID, timestamps, platform and exit state.
For example:

```powershell
python -m research.harness.exclusive_run `
  --label EXP-JAC-002-development-rerun `
  --audit research/results/EXP-JAC-002/formal-run-audit.json `
  -- python research/experiments/EXP-JAC-002/run_experiment.py
```

The lease coordinates cooperating formal runners; it is not a claim that the
host is otherwise idle. While it is held, do not start CI, benchmarks, Julia
tests, compilation, package installation, or other CPU/memory-heavy work. A run
with overlapping host work is infrastructure-invalid for wall-time gates even
when its semantic and oracle-work artifacts remain useful diagnostics.

### Independent host observation

`observe_formal_host` is an independent process, never the parent or wrapper of
the formal runner. Start it in terminal A and wait for both its `HOST-OBSERVER
READY` line and exclusive ready receipt. Only then start `exclusive_run` in
terminal B. Do not use either terminal for other work until observation ends.

The Windows backend uses only Python's standard library and one persistent
PowerShell 7 inventory child. A capability-gated `System.Management`
subscription first attempts `Win32_ProcessStartTrace`; hosts that deny that
provider use an explicitly recorded `__InstanceCreationEvent` fallback. The
fallback is polling-based and does not claim capture of every sub-interval
process; unexplained aggregate CPU remains an independent fail-closed check. It
permits the exact lease-owner process tree, excludes the observer from
per-process checks, and fails closed on other
Julia/Python/compiler/benchmark/package-manager work, configured CPU or memory
pressure, unexplained system-wide CPU, lease loss, excessive polling gaps,
backend stall/exit, PID/topology mismatch, or output overwrite. It reads only
the outer-run audit and `capture.json` metadata; it
does not open segment traces or numerical outcomes.

For EXP-JAC-003, run the observer from its independent worktree in terminal A;
never copy it into or modify the frozen experiment worktree. The ready and host
paths must not already exist:

```powershell
Set-Location C:\solver-worktrees\jac003-host-observer
C:\Users\bakat\miniforge3\python.exe -m research.harness.observe_formal_host `
  --schema-version exp-jac-003-host-observation/v1 `
  --capture-schema exp-jac-003-formal-abba-capture/v1 `
  --segment-count 4 `
  --label EXP-JAC-003-development-abba `
  --observer "Codex subagent /root/jac003_host_plan" `
  --outer-audit C:\solver-worktrees\exp-jac-003-inputs\research\results\EXP-JAC-003-development-formal-run-audit.json `
  --capture C:\solver-worktrees\exp-jac-003-inputs\research\results\EXP-JAC-003-development-abba-staging\capture.json `
  --lock "$env:LOCALAPPDATA/GeoTarget/formal-performance.lock" `
  --ready C:\solver\research\results\EXP-JAC-003\development-host-observation.ready.json `
  --output C:\solver-worktrees\exp-jac-003-inputs\research\results\EXP-JAC-003-development-host-observation.json `
  --powershell "C:\Program Files\PowerShell\7\pwsh.exe" `
  --poll-seconds 2 --max-poll-gap-seconds 5 `
  --cpu-heavy-cores 0.25 `
  --memory-heavy-bytes 2147483648 `
  --memory-growth-bytes 536870912 `
  --unexplained-cpu-cores 1.0 `
  --event-within-seconds 0.1 `
  --backend-stall-seconds 15 `
  --timeout-seconds 86400
```

The ready and final receipts bind every threshold and interval, canonical input
and output path, PowerShell executable/hash/version, snapshot script hash, and
parent/event capabilities. The final receipt also binds the terminal
outer/capture hashes, every observed formal `(PID, creation-time)` identity and
its canonical digest, maximum polling gap, unexplained aggregate CPU maximum,
and the raw inventory stream digest. Success requires every formal descendant,
not only the outer and four segments, to be absent in two consecutive complete
snapshots after lease release. Any nonzero event count makes the observation
unusable by the frozen finalizer.
