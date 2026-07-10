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
