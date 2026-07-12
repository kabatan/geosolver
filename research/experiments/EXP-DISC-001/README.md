# EXP-DISC-001 amendments

The original experiment card remains the preregistered source for discovery
candidate selection. `current-policy-amendment.json` adds the production H0
coordinator and its Halton source as mandatory controls. This prevents an
experiment over new algorithms from silently forgetting the solver behavior it
would replace.

`qmc-prefix-amendment.json` records the preimplementation audit of that control
and of the randomized-QMC and soft-ordering candidates. It fixes the exact
single-128-column prefix construction, separates Owen and Matousek scrambling,
limits IID capture claims to their stated independence model, and makes
deferred-launch liveness auditable at action, launch and completion boundaries.
It also preserves the current refinement-exhaustion behavior as an exact H0
control while requiring a nonblocking research counterfactual and dedicated
counterexample family; that counterfactual cannot directly change production.
`local-champion-dependency-amendment.json` (A3) prospectively replaces only the
now-impossible instruction to freeze an EXP-LOCAL-001 champion. EXP-LOCAL-001
closed without a formal result or product selection. A3 therefore requires a
current-core chain: terminally decide EXP-LOCAL-003 and freeze its locked-pass
scaling policy or explicit `L0-SEMANTIC`; preregister and run the separate
native-globalization study EXP-LOCAL-004 with that frozen policy; then create an
outcome-bound local-champion freeze record. A rejected, inconclusive, protocol-
failed or infrastructure-failed scaling study falls back to `L0-SEMANTIC`; a
globalization study without a locked-passing candidate falls back to current
LM-QR while retaining any independently locked-passing scaling policy. The
chain never selects a non-gating pilot or development-only winner.

`local-finalist-amendment.json` (A4) was written after the independent local
wave selected `E4-EXP-GUARD-SLACK-CPQR`, but before any discovery input,
proposal matrix or outcome existed. It changes only the common local pipeline
used by every discovery arm: `prod-tol-120x600` LM-QR, E1 on guardless
endpoints, and E4 on endpoints exposing public strict guards. The route uses
only a public numerical capability count. A4 preserves the EXP-LOCAL-003/004
fallback decisions as upstream evidence and does not change a proposal stream,
budget, metric, gate or tuning round.

`execution-environment-amendment.json` (A5) adds the already-pinned
`GeoTargetBase` package as a direct project dependency before any proposal
materialization. No package or algorithm version changes. This lets the T0
runner reuse the audited DISC artifact/corpus code and the frozen E1/E4 source
in one environment instead of maintaining a duplicate cross-environment
reader.

The original card and all five amendments form one preregistration bundle.
No EXP-DISC-001 candidate input, assessor input or proposal matrix may be
materialized until the champion freeze record exists. Every downstream
artifact must record the original, A1, A2, A3, A4, A5 and champion-record hashes plus
the exact selected local-solver source and canonical-options hashes.

The amendment was written after a small non-gating six-instance diagnostic.
That diagnostic is deliberately excluded from development and locked inputs,
does not set a threshold, and cannot support promotion or rejection. Formal
inputs, proposal traces and local outcomes must be generated and frozen in a
later commit before the experiment is run.

The A2 audit inspected committed source and primary or official documentation
only. A3 inspected the terminal EXP-LOCAL-001 governance record and the
preregistered EXP-LOCAL-003 card as upstream dependency evidence. No
EXP-DISC-001 proposal matrix, formal input or outcome existed or was inspected
while either amendment's choices were written. A3 and A4 preserve every discovery
method, threshold, budget, control and gate from the original card, A1 and A2,
and has no product connection.

## 2026 Linux implementation checkpoint

The experiment-local Julia project now pins QuasiMonteCarlo and implements the
Stage-A materialization seam, but it deliberately does not contain a proposal
matrix or solver outcome. `run_t0.jl` checks the full preregistration chain
before it loads a corpus, generates a point, creates an output directory, or
invokes a solver. `local-champion-freeze-record.json` now binds the selected
local source, every local option, and the unchanged 512/768-bit authority. The
next checkpoint is proposal-matrix materialization followed by the single
pipeline audit required before outcome execution.

The seam supports the preregistered D0 IID, deterministic Sobol, contiguous
production Halton, current raw counter/Halton mix, Owen- and
Matousek-scrambled Sobol, and the fixed 25% IID / 75% Owen stream. Every method
is specified as one 128-column maximum matrix; checkpoints 8/16/32/64/128 are
leading views of the persisted lossless Float64-bit artifact. The mixed stream
can only consume separately persisted D0 and Owen artifacts. It cannot
regenerate either source.

The current raw mix is an attribution stream, not a replacement for the
mandatory adaptive `D-H0-CURRENT` control. The fixed-source screen may proceed
after its local freeze, input checksum manifest, scorer/accounting audit and
explicit outcome authorization are committed. The complete adaptive H0 and
512/768-bit production comparisons remain later gates; T0 cannot substitute
for either one. Targeted tests materialize all seven sources only in temporary
directories and never inspect a locked/blind partition.

## Stage-A T0 source screen

The first source screen is deliberately non-promotional: six frozen MultiRoot
development cases, one preregistered replicate, seven point sources, and all
128 starts. It records proposal prefixes `8/16/32/64/128` and independently
recomputes the first completed-attempt crossings of callback work
`600/1200/2400/4800`. A favorable T0 row is only a mechanism signal; formal
selection still requires the preregistered multi-replicate, unrelated-family
development comparison.

`materialize_t0.jl` writes one lossless maximum-prefix artifact per
case/source and a small committed checksum manifest before outcomes.
`run_t0_outcomes.jl` then connects those starts to the frozen E1/E4 policy in
one thread per pinned case process. `aggregate_t0.py` independently rescans raw
attempts. The DirectAnalytic T0 laboratory cannot perform production C2
512/768-bit replay, so every T0 artifact states `lab_confirmation_512_768=false`
and cannot promote a public answer. The selected source must later pass the
compiled production integration and its existing 512/768-bit authority.
