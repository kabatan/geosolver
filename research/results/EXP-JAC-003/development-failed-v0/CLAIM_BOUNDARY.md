# EXP-JAC-003 failed-formal claim boundary

## Decision

This capture is closed as a **terminal infrastructure/protocol failure**.  It
failed in the frozen safety assessor before K0 preflight and before any ABBA
segment.  No formal retry is authorized by this closure.  `locked=false` and
`product_connected=false`.

## What was established

- The raw partial directory, outer audit, host receipt, pre-binding audit, and
  observer-ready receipt are hash-bound by `forensic-analysis.json`.
- The exact frozen assessor bytes were hash-verified and executed.
- The official gzipped truth was checked against both the official manifest
  and source lock before it was parsed.  The frozen assessor read its safety
  reference matrices and statuses; no individual reference value is emitted.
- On a deep copy only, matrix-entry values whose exact Python type was `int`
  were converted to `float` only for the observed values {1}.
  The normalization count was 61123.
- The frozen safety assessor returned `passed=false`
  with aggregate counts:

- `dense_analytic_mismatch_count`: 6
- `dense_colored_mismatch_count`: 0
- `fallback_coverage_failure_count`: 0
- `incomplete_pattern_undetected_count`: 0
- `outside_support_nonzero_count`: 0
- `safety_failure_status_count`: 0

## What was not established

- No K0 or K1 segment ran; the partial archive contains zero segment traces.
- No segment trace or K0 control outcome was opened.  No scalar target Gold
  value, safety-reference value, or individual case value is reported by this
  forensic closure.
- There is no ABBA timing, correctness, coverage, speed, or efficacy conclusion.
- The safety-only aggregate is not evidence that the candidate improves the
  solver and does not authorize product integration.
