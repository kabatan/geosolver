# Endpoint/full-replay gate preregistration

This is a bounded, aggregate-only prototype gate over the seven sources that
activated in the frozen prevalence scan.  It is not a formal authority run.

The runner associates each frozen input with the same-stem stored artifact,
reads at most 64 saved HP endpoint plans per source, and first runs the
barycentric exact reconstruction plus untouched-source prototype replay.  It
does not open the stored baseline `RESULT.json` unless that source has already
produced a candidate-ready hold.  It then counts only whether the accepted
baseline envelope contains any existing exact target.  It never emits a path,
ID, expression, endpoint, target, descriptor, or per-source outcome.

Fixed positive gate:

- exactly 145 inputs and exactly seven activated sources;
- at least two candidate-ready sources;
- at least two prototype pure-gain sources spanning at least two source
  signatures;
- zero candidate replay failures, authority/release violations, malformed
  post-ready baseline envelopes, or pre-ready baseline reads.

Even a pass returns `GO_PROTOTYPE_FULL_REPLAY_HOLD`, with authority and target
release false.  It does not invoke the canonical formal authority and cannot
be scored.

## Prepared command (do not run without CPU custody)

```bash
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
timeout --signal=TERM --kill-after=5s 120s \
taskset -c 14 /home/kabatan/work/solver/.venv/bin/python \
  run_endpoint_full_replay_gate.py \
  --source-root /home/kabatan/work/solver-experiment-results/formal-control-development145-180-seed0/inputs \
  --artifact-root /home/kabatan/work/solver-experiment-results/formal-control-development145-180-seed0/artifacts \
  --output /home/kabatan/work/solver-experiment-results/barycentric-area-quotient-endpoint-gate-v1/RESULT.json
```

The output directory must be created once by the benchmark owner before the
run and must not already contain `RESULT.json`.  Runtime dependencies are the
frozen source/artifact roots, this candidate and prevalence scanner, Python
3.12 with SymPy, and the standard library.  NumPy/SciPy/Jupyter/Julia and the
formal scorer/authority are not imported.

## One-shot result

The assigned CPU14 run reproduced 7 activated sources, 73 activated endpoints,
and all 4 signatures among 989 bounded saved endpoints.  The exact candidate
was ready on 0 sources and emitted 0 proposals.  Consequently the
candidate-first custody rule opened 0 baseline terminals.  Replay failures,
authority/release violations, malformed sources, and malformed post-ready
baseline envelopes were all 0.  Decision: `STOP_ENDPOINT_GATE`; no tuning or
retry was performed.

The repository-external aggregate result SHA-256 is
`9af24c19b317fd267ee651afce99604c434570a0e3e840c290f294ef48c111df`.
The only reopen condition is a new endpoint where an exact bounded-CF
barycentric witness passes the untouched-source replay; numeric rational-Area
activation alone is not a reopen signal.
