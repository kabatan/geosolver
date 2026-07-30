# EXP-GLOBAL-001 evidence ledger

This ledger is deliberately aggregate-only.  Raw case artifacts and truth stay
outside Git, and validation/sealed inputs have not been opened.

| Mechanism | Evidence | Disposition | Reopen gate |
|---|---|---|---|
| Frozen common control | Reproduced safely on the common harness.  Screen24 seed 0 is 16/24; the exact entrypoint SHA-256 is `e1405739...c7301`. | Formal control. | Replace only if a stronger arm is reproduced under the identical harness. |
| Clean `0967ff1c` transplant | 15/24, one rejected worker result (`search artifact is absent at reservoir commit`), and about 4.9% slower than control. | Rejected on safety, recall, and speed. | Demonstrate a fail-closed reservoir commit and rerun S0 before any screen. |
| Fixed progressive profiles `[64,192,600]` / `[96,300,600]` | 14/24 and 13/24, but both wrappers accidentally used direct finalist-v15 rather than the exact common-control stack. | Measurements invalid for mechanism attribution; arms retired. | Exact-control binding plus a no-op differential; satisfied only by the adaptive hybrid successor. |
| Adaptive progressive hybrid | S1 nets are `[+2,+2,-1]`; S2 seed 0 development145 is 116/145 versus 113/145, wins/losses `5/2`, wall ratio `0.9627`, safety zero, family-fold nets `[+2,+1,0]`. | Sole S2 survivor; frozen for S3. | No tuning from S2 case identities.  Any mechanism change creates a new arm/hash and returns to S0. |
| Multi-target v1-v3 | 14/24, 15/24, 15/24, but the wrappers used the wrong direct-v15 baseline. | Invalid mechanism comparison; retired. | Exact common-control result union and byte-identical no-op path. |
| Multi-target v4 exact-control union | 16/24 tie, 24/24 accepted, negligible wall change, but no side-route activation on screen24. | Stopped at the S1 zero-activation gate. | A truth-blind applicability predicate with generated and screen activation, while retaining the byte-identical common path. |
| Rank chart v1 | Seed 0 tied 16/24 and activated on 5/24; seed 1 fell to 14/24 versus 16/24. | Rejected for recurring recall risk. | The trust-radius v2 generated gate (`48/156` to `57/156`, no generated-family regression) is a distinct candidate and still requires formal S1. |
| Incremental evaluator | Microbenchmark speedup was 1.146x with identical ordering/bits.  The first full wrapper exceeded the 30 s budget; the isolated deadline arm later scored 14/24 versus 16/24 and was about 13.8% slower. | Rejected as an end-to-end arm. | A bit-identical hook below the existing deadline owner, plus end-to-end speed gain on screen24 without recall loss. |
| Cached sparsity evaluator | Signed-zero mismatch and an unsafe child hook were found before formal screening. | Blocked at S0. | Bitwise equality including signed zero and a fail-closed hook owned by the canonical evaluator. |
| Block-triangular structure | Static applicability was 27/145 and generated work dropped sharply, consistent with nonlinear block-triangular decomposition, but the first connected polynomial side route scored 15/24. | Useful structural primitive; not a survivor by itself. | A concrete small-block solver that preserves a fixed numerical-baseline quota and improves generated recall. |
| Strict whole-problem polynomial route | Safe recognizer activated on 0/145. | Closed for this corpus. | A sound block-local recognizer; never weaken polynomial soundness merely to raise activation. |
| BTF to polynomial leftover route | Static combined applicability was 9/145.  v1 scored 15/24.  The v2 formal run is invalid because its mechanism file changed before the final cases completed. | No formal conclusion for v2; invalid run must not be cited as evidence. | Freeze the final exact-control hash before a clean rerun; no edits during measurement. |
| Interval/Krawczyk route | Safe low-dimensional interval extension activated on 0/145 because explicit bounds were absent and opaque calls dominated. | Closed for this corpus. | A sound interval extension with nonzero generated and development activation; canonical replay remains mandatory. |

The structure lanes follow the cited ideas rather than claiming a complete
implementation of their research systems: nonlinear block lower-triangular
reordering/solution, geometric decomposition-recombination planning, small
polynomial-system solving, and interval/Krawczyk certification.  Their side
routes are always proposals to the existing canonical verifier and retain a
numerical-baseline quota.

Primary references:

- Dennis, Martínez, and Zhang, “Triangular Decomposition Methods for Solving Reducible Nonlinear Systems of Equations,” DOI `10.1137/0804020`.
- Sitharam et al., “Optimal Decomposition and Recombination of Isostatic Geometric Constraint Systems for Designing Layered Materials,” arXiv `1507.01158`.
- Berthomieu et al., “msolve: A Library for Solving Polynomial Systems,” arXiv `2104.03572`.
- `IntervalRootFinding.jl` internals for interval Newton/Krawczyk classification.

## Current gate state

- S0/metamorphic/differential tests: 99 passed after integration.
- S1: adaptive hybrid survived; other formally measured mechanisms stopped or
  remain explicitly unqualified.
- S2: adaptive hybrid passed the family-disjoint development145 cross-check.
- S3: pending a launcher CPU/RSS telemetry preflight; the candidate mechanism
  hash is frozen.
- Validation/sealed: unopened.
