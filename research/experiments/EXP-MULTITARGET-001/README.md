# EXP-MULTITARGET-001: post-answer diverse tail

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

`arm.json` follows the common campaign contract: its entrypoint is relative to
the manifest and `mechanism_hash` is the SHA-256 of `worker.py` bytes. The
frozen common runner accepts the final v15 result schema; overlay identity and
mechanism digests are carried by the worker dry plan.

Run the truth-free counterexample/metamorphic S0 with:

```bash
/home/kabatan/work/solver/.venv/bin/python \
  research/experiments/EXP-MULTITARGET-001/run_metamorphic_s0.py
```
