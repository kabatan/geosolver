# Source-only smoke ledger

Date: 2026-07-31 (Asia/Tokyo)

Scope: synthetic source dry-runs and unit tests only. No `--execute`, scorer,
truth data, real case outcome, or formal CPU was used. Every Python process was
pinned by `taskset -c 31`; the dry plan's `--cpu 15` value only satisfies the
historical first-sibling CLI schema and launches no child in dry-run mode.

Fixed environment: `/home/kabatan/work/solver/.venv/bin/python`, Python
3.12.11, NumPy 2.5.1, SciPy 1.18.0, mpmath 1.3.0, SymPy 1.14.0.

## Unit/source checks

- 6 tests passed: historical POC HP captured exactly once, zero-authority
  object identity retained, ready ordinary authority rejected when the exact
  tail cannot run before deadline, malformed success rejected, matching exact
  descriptor published instead of the ordinary descriptor, and conflicting
  global mode rejected.
- Candidate positive-dimensional dry plan: global
  `CONFIRM_ALL_AUTHORITIES`, capture count 1, ordinary bypass false.
- Candidate zero-dimensional dry plan: existing
  `source_exact_zero_dimensional` route, authority logic changed false.
- Default `exact_outer_decorator/worker.py` positive-dimensional control dry
  plan: global `CONFIRM_ALL_AUTHORITIES`, capture count 1.

## Reproducible dry PLAN hashes

The output paths were fixed below because the absolute output path is part of
the PLAN. Repeating the candidate positive dry-run at the same path produced
the same hash.

- Candidate positive: `666ea353b399c1b68e4e2b3daf382b08009b359d023de73505387ef6272bb5e9`
- Candidate zero: `fef49b3a6d981af408e27ec3dc97d76599ddf086910b3b982d68ab38a299f7c0`
- Default exact-outer positive control: `03b94044524df4714fc0d244dc41b3248309f7086d3e1f9b1c18e08c64dd99d2`

Raw smoke artifacts are outside Git under
`/tmp/geotarget-archive-exact-outer-source-smoke-v1/`.
