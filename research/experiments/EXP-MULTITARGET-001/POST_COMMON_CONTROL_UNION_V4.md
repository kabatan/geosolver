# EXP-MULTITARGET-001 exact common-control result union v4

## Corrected baseline

The formal common control is not numerical-v15 directly. Its top-level
entrypoint is:

`research/experiments/EXP-V15-243-001/repro_20260722/workers/champion_v2_poc_preloaded.py`

at SHA-256
`e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301`.
It loads champion-v2 zero-dimensional authority, champion-v1/v0 target-free
reservoir and repeated batch service, periodic PointOnCircle semantics, the
approved HP bridge, and precision runtime preload. V1-v3 are therefore retained
only as baseline-mismatch evidence.

## V4 mechanism

- Entrypoint SHA-256:
  `740f57f83919da17a25342bbdd279ef170cf3ba194fc22b4aa70c04501431415`.
- Control adapter SHA-256:
  `c67c9bce374638b78852332c1cd875f4b0bb157cd9c6ca1b92ad5da35b213c1b`.
- V4 checks the top-level control and eleven principal closure files, including
  periodic v1/v2 wrappers, precision preload, champion v0/v1/v2, reservoir,
  search worker, approved HP bridge, and v15 base.
- It calls the exact control `main()` with original argv. No control function,
  constant, deadline, Python path, periodic semantic, preload, or PLAN is
  patched.
- Dry runs return immediately, so the v4 PLAN is the common-control PLAN bytes.
- Execute runs first retain the completed control RESULT byte-for-byte as
  `COMMON_CONTROL_RESULT.json`, even when no side window exists.
- Zero-dimensional sources stop after the control snapshot. Positive-dimensional
  side admission requires `0.1 replay + 3.0 HP + 2.0 union reserve` seconds of
  wall measured from the common control BASE's original `PROCESS_STARTED`.
- Side replay uses the final champion-v0 reservoir seam. Its intentionally
  unknown provisional targets are mapped to a neutral value only in copied
  side candidates, making ordering configuration/residual-only. Baseline and
  exact authority remain untouched.
- The hash-bound v3 union core admits at most one side HP and publishes only a
  novel canonical descriptor-key set union. Duplicate/failure/no-candidate/
  reserve exhaustion leaves RESULT equal to the common-control snapshot.

## Truth-free tests

Six v4 tests verify:

- exact control closure digests;
- direct-control and v4 dry PLAN byte equality in separate processes;
- common-control RESULT snapshot byte equality;
- correct handling of champion-v0 delayed `provisional_target=None` candidates;
- exact argv forwarding except the overlay-only control-root option;
- absence of control-surface patches and truth/case/known-target-count reads.

Together with retained multi-target tests, 34/34 pass. No scorer, expected
descriptor, answer value, validation, sealed data, or formal corpus result was
used.

## Source-only end-to-end smokes

All smokes ran `direct control dry → v4 dry → v4 execute` with identical
source, seed, budgets, CPU, and output path. Direct and v4 PLAN SHA matched.

1. Generated single-target source, seed 0, 15/6 seconds, 8 starts × 64
   callbacks: PLAN `9f71b89a…`; common-control snapshot and final RESULT both
   `97c99d11…`. Replay found no unattempted candidate.
2. Generated two-target source, seed 0, 15/6 seconds, 64 starts × 96
   callbacks: PLAN `0d3f51cb…`; snapshot/final both `62172432…`. Side HP was
   attempted from real slack but produced no novel canonical descriptor, so
   RESULT remained byte-identical.
3. Actual source-only SHA
   `63fb3e07117c47ee18aa18cbb2e891578e84c1d8e3fb8dc1d3b26b777a70b1c0`,
   seed 0, 15/5 seconds, 16 starts × 32 callbacks: PLAN `a58eae34…`;
   snapshot/final both `744ab6b6…`. The common control returned with less than
   the minimum side window, so no side directory was created.

All RESULTS preserve v15 schema, source bytes, and wall-budget validity. Raw
artifacts are outside Git.

## Promotion and stop gate

The selected `arm.json` is intentionally unchanged. The benchmark owner may
bind `arm-v4.proposal.json` only after checking, without case disclosure, that
every candidate run contains `COMMON_CONTROL_RESULT.json`, its descriptor keys
are a subset of final keys, and no-union runs have equal snapshot/final SHA.
Any mismatch, malformed output, safety failure, or deadline miss closes this
lane. V1-v3 must not be promoted as substitutes for this common control.
