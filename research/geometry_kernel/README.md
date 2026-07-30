# Geometry kernel qualification harness

This directory contains the product-independent measurement tools used by the
geometry-kernel arms. Raw results belong under
`/home/kabatan/work/solver-artifacts/geometry-kernel/<run-id>`; they are never
written into a worktree.

`measure_callbacks.py` freezes a deterministic input stream for every problem,
records bitwise residual and complete-callback digests, and measures wall time,
CPU time, callback throughput, peak RSS, and completed callbacks. Routing is
reported only from backend mode, typed opcodes/effects, and selector metadata.

`compare_same_work.py` rejects mismatched inputs or observations before
reporting family-clustered ratios. It deliberately has no problem-ID allowlist
and treats any structural-class regression as a failed arm.

Set `GEOTARGET_BENCH_REPOSITORY` to the absolute worktree under test. This
keeps the harness bytes fixed while control and candidate import their own
product code.

The final solver ABBA remains the exported, hash-pinned `EXP-GLOBAL-001`
orchestrator. This harness is the faster S0/S1 gate used before an arm is
allowed to consume a screen24 or 145-problem solve run.
