# D0 Result

- Date: 2026-07-31
- CPU custody: CPU14 exclusively assigned by benchmark owner
- Interpreter: `/home/kabatan/work/solver/.venv/bin/python`
- Native-thread caps: `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`,
  `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`
- pytest: 7 passed in 0.12 seconds
- generated positives ready: 3/3
- generated positives with full exact-prototype replay: 3/3
- translation/scale barycentric signature invariant: true
- wrong endpoint baseline fallback: true
- authority passes: 0
- target releases: 0
- decision: `GO_STATIC_TEST`

This run used only generated sources.  It did not inspect truth, scores,
individual corpus outcomes, endpoint census rows, or formal/full replay data.
It does not authorize target release or claim canonical correctness.
