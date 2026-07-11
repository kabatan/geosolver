# ALG-LAB-000 — Linux measurement baseline

Status: **complete diagnostic baseline** (2026-07-12).

The solver laboratory now emits `geotarget.solver-experiment/v2`. It retains
the historical endpoint metrics and separately records solver-reported
accepted target recall, accepted-endpoint safety, a fixed common endpoint
assessor, local-versus-runner evaluation caps, reported/observed count
differences, and suffix-stable work to safe full-target recovery.

The three frozen controls are `legacy-lab-120x600`,
`prod-tol-120x600`, and `prod-options-250x2000`. Their clean Linux run is
bound by
[`linux-m1-baseline-2026-07-12.json`](../../benchmarks/manifests/linux-m1-baseline-2026-07-12.json).
The ignored raw artifact has SHA-256
`981e03141d40b60b633107f1a422f4ce363fad3a81fa3d13f8f5027258e3762a`.

An independent raw reaggregation checked all 216 attempts and all 81
summaries, including every prefix-8 summary, with zero mismatches. The final
audit checksum is
`7709c97b299897b2377e49114f37e886d0d778773f512c3dc7a5e2f536f0f3e8`.

The first audit found that the original callable closure exposed captured
analytic roots through reflection and allowed direct callback-cap bypass. The
runner now gives every family the same token-only opaque evaluator type; all
calls, including direct evaluator calls, pass through the counter, and expired
tokens fail closed. This is a source-audited in-process research boundary, not
a hostile-code sandbox. A candidate that deliberately accesses private
`GeoTargetBenchmarks` oracle storage must be rejected by source audit; hostile
third-party candidate execution would require a subprocess/RPC boundary.

At prefix 8 the fixed-assessor safe-full counts were 1/9, 6/9, and 6/9 for the
three controls respectively. These are measurement controls, not a local
algorithm promotion decision.
