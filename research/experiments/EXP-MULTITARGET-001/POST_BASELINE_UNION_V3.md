# EXP-MULTITARGET-001 full-worker result union v3

## Hypothesis

Independent control/candidate runs can differ even when a scheduler overlay
preserves the frozen pre-answer trace. A loss-safe multi-target mechanism must
make the frozen result a concrete prefix of the candidate result in the same
process: first finish and retain baseline bytes, then perform optional side work
without shortening or rerunning baseline HP/restoration.

## Mechanism and applicability

- `worker_v3.py` hash-loads frozen numerical-v15 at SHA-256
  `330e52c75b98d3c58a1422cec415b5a53673ebafb7e90789a271df34a308309d`.
- It patches no function, constant, deadline, Python path, plan, or frozen argv.
  Frozen `main()` writes the ordinary PLAN and complete RESULT before v3 code
  observes any endpoint or descriptor.
- Entrypoint SHA-256:
  `1a16a60b854960c69d523d8cc30189726c5f48f29428fd6ea30a7c903f124798`.
- Union mechanism SHA-256:
  `48b51f82803c5b41490ad24206527e96be87bcab46d9b965369519357b0f99e7`.
- If measured slack is below `0.1 replay + 3.0 HP + 2.0 finalization`
  seconds, the wrapper returns immediately without reading or writing RESULT.
- With admissible slack, source SHA and frozen RESULT accounting are rechecked.
  Existing search endpoints are replayed for at most one second; every endpoint
  already present in baseline `hp_attempts` is excluded.
- Before side HP, baseline RESULT bytes are atomically retained as
  `BASELINE_RESULT.json` and read back for equality. One truth-free diverse
  candidate may receive at most six HP seconds. Its own failed authority can
  enter frozen restoration only if three seconds plus the two-second union
  reserve remain. Baseline HP/restoration is never rerun.
- Only a novel canonical descriptor key can rewrite RESULT. The baseline
  attempts remain an exact list prefix and baseline descriptors a set subset.
  No-novelty, reserve exhaustion, or late union write restores/leaves baseline
  RESULT bytes unchanged.

This mechanism applies only when frozen v15 naturally returns at least 5.1
seconds before its hard deadline and replay retains an unattempted endpoint.
It does not reserve time to manufacture applicability.

## Truth-free preservation and deadline evidence

Ten v3 tests use deterministic clocks and synthetic source/search/result
artifacts:

- no-slack RESULT byte equality and zero side calls;
- replay with no unattempted candidate leaves bytes equal;
- side failure/restoration with no novel descriptor leaves bytes equal;
- duplicate side authority leaves bytes equal and does not trigger restoration;
- successful union retains the baseline bytes, HP-attempt prefix, descriptor
  subset, and original frozen schedule fields;
- every admitted timeout leaves the two-second finalization reserve;
- a simulated late atomic union write restores the byte-exact baseline;
- side ranking is candidate-permutation and invertible target-affine invariant;
- v3 and direct frozen dry PLAN bytes are equal at the same path;
- wrapper source contains no frozen-surface patch and the mechanism has no
  truth/case/known-target-count read.

All EXP-MULTITARGET tests pass, 28/28. No scorer, formal corpus, validation,
sealed data, case identity, or benchmark truth was used.

## Generated full-worker smokes

The two-root circle construction is generated and carries no external truth.
At 15 seconds total/6 seconds search, frozen v15 first materialized one HP
attempt and one exact descriptor in 6.4931 seconds. The snapshot SHA-256 is
`2e021c69de5627cb897ed95a5536ff073b987ae50575f720d9d16280e855e3ec`.
One side HP attempt added a second exact descriptor; final elapsed was 7.4195
seconds, `within_total_wall_budget=true`, and the baseline snapshot remained
byte-identical. Final SHA-256 is
`b56bff11495bf672af9361f1157e8747d3fd4c853798da10a9c4dc80c952cf83`.

A separate 7/1-second generated smoke had no admissible side window. V3 took
the immediate frozen-only return: no snapshot, no side directory, no union
metadata, and ordinary RESULT SHA-256
`7016d2c6cd203ac0354b954cd8260a228ae7ee8bce50864d095450dc7b3e54a3`.
Raw artifacts remain outside Git.

## Promotion and stop gate

`arm.json` is deliberately unchanged. The benchmark owner may bind the proposal
only after independently verifying common-runner acceptance and the per-run
invariant `baseline exact keys ⊆ final exact keys` from candidate-owned
snapshots, without disclosing cases. Any subset violation, baseline trace-prefix
violation, malformed/extra output, or deadline miss permanently closes this
multi-target lane. Formal wins/losses alone must not reopen scheduler changes.
