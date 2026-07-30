# EXP-MULTITARGET-001: post-answer tail experiments

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
