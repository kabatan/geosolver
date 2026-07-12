# EXP-LOCAL-008 — poll-only OrthoMADS/extreme-barrier comparator

Status: **rejected at T0; no T1, Core integration, or production promotion**

This experiment tested a pure-Julia deterministic poll-only OrthoMADS local
solver after Powell HYBR failed T2. The truth-blind mechanism used normalized
finite-box coordinates, declared residual scaling, adjusted Halton directions,
the scaled Householder basis `H = ||q||²I - 2qq'`, complete `2n` polls, and an
extreme barrier for invalid/domain evaluations. It had no model, surrogate,
search step, or result-dependent solver fallback.

The outcome-independent corpus and gate are preserved in
[`preregistration.json`](preregistration.json). Six cases covered Curved,
NearRank, Tangent, two Warped target maps, and on-boundary StrictGuard. Primary
work was common-assessor suffix-stable safe-full callbacks, right-censored at
4,800 per case.

The audited T0 recovered one target versus five for the control, no safe-full
case versus two, and used `1.4723926380` times its work. Two StrictGuard
boundary-ghost endpoints were Gold-inconsistent. Path A, Path B, safety, and
StrictGuard gates all failed.

[`t0-decision.json`](t0-decision.json) is authoritative. Candidate code,
dependency files, runner, tests, and knobs were removed after rejection; the
committed execution revision named in the decision retains them for audit.
