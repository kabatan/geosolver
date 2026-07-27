# Champion pipeline reproduction — 2026-07-27

## Defect found and corrected

The first product implementation validated V15 constraints with a Pydantic
`float | str` field and then passed the model dump to the engine. JSON integer
constraint values therefore changed from `4` to `4.0`. The source SHA changed,
and champion's exact replay authority correctly rejected the altered source.

The product now treats validation as inspection only and materializes the
original JSON object without scalar coercion. It also restores the frozen
native-thread environment and the original guarded subprocess limits used by
the 2026-07-22 runner. No champion threshold, proposal order, start count,
callback limit, precision, restoration rule, or exact-authority rule changed.

## Verification

- Product solver commit under test: `6c22b09fc5e4a977e312ee98dd94a163d5f7a717`
- Subsequent main commits add only the regression test and documentation after
  that run; the solver execution path is unchanged.
- 145/145 processes accepted; timeout/crash: 0.
- Seven-lane one-shot truth score: 130/145; false/extra exact: 0.
- One-shot descriptor sets equal to the archived frozen run: 138/145.
- Three descriptors absent from the archived run were all true targets.
- Four archived descriptors missed in the one-shot run were rerun through the
  unchanged one-core reference mode; all four matched the archived descriptor.
- Reference-isolation truth score: 134/145; false/extra exact: 0.
- Archived frozen descriptors unreproduced after isolation: 0.
- Reference-isolation median: 142.43 s versus frozen 138.07 s (+3.2%).
- Reference-isolation p95: 178.38 s versus frozen 177.04 s (+0.76%).

The local HTTP product executes solve jobs FIFO. The seven-lane run remains a
useful stress observation: wall-clock scheduling can change which fixed work
items finish in the 180-second window. The isolation audit is the reference
product-contract check and reproduces every descriptor returned by the frozen
champion without adding a solver retry or using truth during execution.

## Evidence

- `RUN_RESULT.json`: raw seven-lane aggregate
- `PAIRED_COMPARISON.json`: product versus archived frozen, case by case
- `truth-score-input/OFFLINE_SCORE.json`: offline truth score
- `REFERENCE_ISOLATION_AUDIT.json`: isolated recovery and checksums
