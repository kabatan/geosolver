# EXP-MULTITARGET-001: post-answer tail experiments

## Proposed research arm: exact-descriptor species racing D0

`species_racing.py` changes only the 25% side-budget allocation after a fixed
75% ordinary prefix. It uses block-incidence Good--Turing/Chao2 estimates from
canonical-authority descriptor history and never changes output authority or
claims completeness. Generated D0 activated on 240/240 cases and improved all
three mechanisms with false/extra zero. The common `arm.json` is unchanged;
see `SPECIES_RACING_D0.md` and `results/species-racing-d0.json`.

Repair A replaces generic side reallocation with a dominance-safe handoff:
only typed redundant, unstarted deep work may be borrowed after independent
descriptor confirmation and high unseen incidence. Its equal-work generated
panel changes descriptor gain/loss from D0's `+170/-13` to `+294/-0` across
five mechanisms. See `SPECIES_RACING_REPAIR_A.md` and
`results/species-racing-repair-a.json`; the common arm remains unchanged.

## Proposed arm: exact common-control result union v4

Integration audit found that v1-v3 used numerical-v15 directly, while the
formal common control is the layered
`repro_20260722/workers/champion_v2_poc_preloaded.py`. That control includes
champion-v0 target-free reservoir batches, champion-v1 HP semantics,
PointOnCircle periodic wrappers, zero-dimensional authority, and precision
preload. V3's snapshot was internally monotone but was not a snapshot of the
formal control.

`worker_v4.py` hash-binds and invokes that exact top-level control without
patching it. Its ordinary PLAN and RESULT are completed first; RESULT bytes are
then retained as `COMMON_CONTROL_RESULT.json`. Only the control BASE's measured
remaining wall can enter the existing result-union core. Three direct-control
versus v4 source-only smokes—including source SHA prefix `63fb3e`—had identical
dry PLAN bytes, and every no-union final RESULT was byte-identical to its
in-process common-control snapshot.

V4 is recorded in `arm-v4.proposal.json`; the selected `arm.json` remains
unchanged for benchmark-owner integration. See `POST_COMMON_CONTROL_UNION_V4.md`.

## Proposed arm: full-worker result union v3

Formal-owner aggregate evidence for v2 was safety-clean and faster on geometric
mean, but still 15/24 versus control 16/24 (one win, two losses; no case identity
or per-case result disclosed). `worker_v3.py` therefore abandons scheduler
patching: it runs frozen v15 to a complete baseline `RESULT.json` first. Only
when the same monotonic deadline has a separately observed admissible slack
window may it retain a byte-exact `BASELINE_RESULT.json`, replay an unattempted
endpoint, and exact-key-union a novel canonical descriptor.

V3 is intentionally not selected by `arm.json`; `arm-v3.proposal.json` records
the candidate binding for benchmark-owner review. Truth-free tests prove frozen
dry-plan equality, no-slack RESULT byte equality, baseline trace-prefix
preservation, descriptor-set monotonicity, and bounded deadline admission. A
generated multi-target smoke expanded one frozen descriptor to two without
altering the saved baseline. See `POST_BASELINE_UNION_V3.md`.

## Current arm: adaptive slack v2

`arm.json` now selects `worker_v2.py`. Formal-owner aggregate evidence for v1
was safety-clean but 14/24 versus control 16/24 (0 wins, 2 losses). No case ID,
truth, or per-case outcome was disclosed. The v1 mechanism reserved six HP
seconds and expanded reservoir replay before any descriptor existed, so it
could shorten baseline discovery/exactification.

V2 removes every pre-answer reservation:

1. Search seconds, starts, callbacks, seed, selection reserve, replay, primary
   tranche, frozen wave order, timeout floats, child interpreter, and paths are
   unchanged.
2. Authority must pass through the frozen canonical verifier before adaptation
   becomes eligible.
3. All frozen primary, alternate, and restoration waves still execute in their
   original order. Only after they complete may unused wall slack service
   deferred reservoir endpoints, capped at six seconds per HP attempt, followed
   by failure-triggered frozen restoration when fast failures leave more slack.
4. If authority never passes, the full service trace is identical to v15 and
   the adaptive lane remains unreachable.

The frozen seam cannot confirm a provisional/exact descriptor during numerical
discovery: confirmation first becomes available in HP service after search and
fresh source replay. V2 therefore does not claim in-search continuation.

Run the v2 trace-equivalence and truth-free metamorphic tests with:

```bash
/home/kabatan/work/solver/.venv/bin/python -m pytest -q \
  research/experiments/EXP-MULTITARGET-001/test_post_answer_v2.py
```

See `POST_ANSWER_V2.md` and `results/post-answer-v2-s0.json` for the frozen
boundary, trace contract, hashes, and generated execution smoke.

## Superseded arm: diverse tail v1

This is a scheduling-only overlay for the hash-bound numerical-v15 champion.
It does not modify discovery, the original-source evaluator, canonical replay,
HP exactification, descriptor authority, or final exact descriptor keys.

The candidate makes four general changes:

1. A normal 180/146 run must retain at least 28 seconds after discovery.
2. Fresh reservoir replay receives three seconds instead of one.
3. An exact descriptor never terminates service of other admitted primaries,
   and same-provisional-target alternates are not suppressed after success.
4. After authority succeeds, remaining work is softly ordered by provisional
   target/configuration distance from the successful candidate, with residual
   quality retained in the score.

The last six seconds of the HP window are kept out of primary tranche sizing so
at least one alternate or failure-restoration attempt can run when present.
Fast primary calls return their unused time to the tail. Deferred candidates
remain explicitly unknown; the worker makes no completeness claim.

The frozen worker is required at the digest recorded in `worker.py`. The
runtime root and Python may be overridden with `GEOTARGET_FROZEN_SOLVER_ROOT`
and `GEOTARGET_EXPERIMENT_PYTHON`, or the corresponding CLI flags. A common
short 30/20 run automatically uses its full 10-second post-search window;
formal 180/146 runs retain the default 28-second minimum. An explicit
`--minimum-tail-seconds` remains available for boundary tests.

Run the generated policy tests with:

```bash
/home/kabatan/work/solver/.venv/bin/python -m pytest -q \
  research/experiments/EXP-MULTITARGET-001/test_candidate.py
```

The 100-panel deterministic S0 comparison is:

```bash
/home/kabatan/work/solver/.venv/bin/python \
  research/experiments/EXP-MULTITARGET-001/run_generated_s0.py
```

The original v1 entrypoint remains as `worker.py` for negative-result evidence,
but it is no longer selected by the common arm.

Run the truth-free counterexample/metamorphic S0 with:

```bash
/home/kabatan/work/solver/.venv/bin/python \
  research/experiments/EXP-MULTITARGET-001/run_metamorphic_s0.py
```
