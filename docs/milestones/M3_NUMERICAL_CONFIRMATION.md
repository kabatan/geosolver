# M3 numerical confirmation checkpoint

Status: numerical gate, optional C3A exactification and outer hard wall
mechanism complete; release corpus campaign remains open

Date: 2026-07-12

Numerical implementation: `c79f0df`

Exact production connection: `f468b5f`

Outer process-tree hard timeout: `525f9d7`, Linux custody hardening: `cc99491`

Owned PSLQ: `c157254`

## Accepted numerical contract

- Float64 discovery remains a separate `1e-12` local process.
- A candidate can become a `ProvisionalAnswer` only with all-path C2 support.
- The original Float64 endpoint is independently refined by the compiled plan
  at 512 bits and by the reference interpreter at 768 bits.
- A fresh 768-bit reference replay must preserve the branch and semantics.
- Scaled residual, normalized coordinate disagreement and relative target
  disagreement must each be at most `1e-100`; refinement targets `1e-110`.
- `h` and `h/2` five-point/one-sided Jacobians must agree on full
  free-variable rank. Rank-deficient exact-zero manifolds are not numerical
  configuration claims.
- High-precision evaluations are charged by `ceil(bits / 53)` and share the
  solve deadline, cancellation token and oracle-work budget.

The gate does not prove interval existence, uniqueness, all-target completeness
or algebraic exactness.

## Independent checks

- Complete Julia integration with `JULIA_NUM_THREADS=2`: green, including
  concurrent artifact determinism.
- Linux `scripts/ci.py --tier Smoke` with the pinned Python 3.12.11 runner:
  green, including governance/research validation, Julia integration, Python
  lint/type/tests and QA-02 deterministic fuzz.
- GeoTargetExact package: full `Pkg.test()` green, including C3A production
  solve, multiple-root exact-only promotion and checkpoint tamper rejection.
- Complete one-thread Julia integration after the exact production connection:
  green.
- Formal-run hard-timeout tests: normal completion, timeout exit 124, orphan
  and new-session descendant custody, strict deadline observation, raw-fork
  zombie reaping, repeated interrupt/SIGTERM cleanup and audit-finalization
  signal handling green on Linux. Windows remains correctness-only and
  platform-gated for this mechanism.
- Independent owned-PSLQ probe: `x^d-p` for `d = 2,3,4,5,6,8,10,12` and
  `p = 2,3`, with identical relations at the base and `+256`-bit precisions.

## Source checksums at the implementation checkpoint

| File | SHA-256 |
|---|---|
| `julia/GeoTargetCore/src/high_precision_refinement.jl` | `e1839b6996656aea7c63275aa51d88cd159bc7563bef3a4cdd83aa639b282c96` |
| `julia/GeoTargetCore/src/candidate_validation.jl` | `5cd036667feb36d9b6ffdc5a335ae0cddebe415d2c47a64d20386e5a6d35bcf6` |
| `julia/GeoTargetCore/src/solver.jl` | `0564f8acc75350ebce7c1be8a87629204a0ff105bb59da345aba543460be4cbe` |
| `julia/GeoTargetExact/src/pslq.jl` | `db1ea954f916641a3113031cd9bd05a09817bb89f56722ee6afe8ae0c981cbcb` |

## Optional exactification contract now implemented

- `GeoTargetExact` remains an optional one-way backend behind
  `GeoTargetBase <- GeoTargetCore <- GeoTargetExact`.
- A regular validated candidate, or a numerically unresolved near-feasible
  hypothesis, may ask the Core-owned sample provider for independent reference
  samples. Hypothesis provenance never authorizes numerical promotion.
- Recognition uses the bounded degree/height ladder at two precisions. PSLQ and
  rational reconstruction only propose algebraic identities.
- Every free variable is reconstructed as an algebraic real and the original
  graph is replayed through C3A. Exact relations, bounds, domains, guards,
  branches and target identity must all pass before an `ExactAnswer` exists.
- Regular and exact-only observations are built from the final Core-owned
  reference sample, not a Float64 discovery endpoint.
- Restored answers are independently reconstructed at 768 bits and bound to
  their stored target identity, branch, endpoint and target enclosure with the
  public `1e-100` gate. Literal rational answers receive the same approximation
  check.
- Backend policy and environment identities are part of resume identity.
  Candidate history and proposed/observed evidence events are cross-checked
  one-for-one before any resumed answer is returned.
- Exactification failure falls back only to an already validated numerical
  answer, with the actual recognition, budget or certificate failure exposed
  in `ProvisionalAnswer`.

The generic rank-deficient refiner uses guarded geometric sequence
extrapolation only to produce better exactification samples. It has no
standalone promotion authority; dual-precision sampling and exact graph replay
remain mandatory.

### Source checksums at `f468b5f`

| File | SHA-256 |
|---|---|
| `julia/GeoTargetCore/src/high_precision_refinement.jl` | `f46a4496979ef9c12bfdcc8075558ef30c5a101ab7238720b5ecb200fc21fed3` |
| `julia/GeoTargetCore/src/exact_backend.jl` | `73158a0fe2e08108f4b2156ff4bf3e561f1fe32aedde6e81d6c4ecc4ea145614` |
| `julia/GeoTargetCore/src/exact_verification.jl` | `17980f4f067a26ec0fe88df3d5f45c60182cbfbe2b09dc8e71997af4998438e0` |
| `julia/GeoTargetCore/src/search_loop.jl` | `91f69cb47300c74c444d2691df89f9d0566669dad67aa3f94e2fd6e1e642ef45` |
| `julia/GeoTargetCore/src/solver.jl` | `ee507bf0b4bb5eb901e9fff51f584b5f205a1e09ca068034f51bdf6dbefca526` |
| `julia/GeoTargetExact/src/backend.jl` | `49f7915fa808e9d5e7674422cc63a5ce5224a172ef344c027a54245a45523173` |
| `julia/GeoTargetExact/src/recognition.jl` | `5024e4572bac1f019d5b4b0daba5c23266d2754e43d3cf6c64928c28f902c253` |

## Remaining M3 work

- Synchronous plugin, Nemo and FLINT calls can only poll cooperatively. Formal
  release runs must therefore invoke each case process through
  `research/harness/exclusive_run.py --timeout-seconds ...`. It terminates the
  Linux process tree under subreaper custody and records timeout exit 124;
  success is accepted only when full-tree exit is observed strictly before the
  monotonic deadline. The in-process API still makes no preemption claim.
  SIGINT/SIGTERM are cleanup-safe; SIGKILL and host failure are outside the
  guarantee. Windows correctness runs remain required, but its `taskkill /T`
  fallback is not release hard-wall evidence.
- Run the frozen exact-eligible corpus and holdouts at the release budgets and
  demonstrate `P_full_exact(180s) >= 95%` with zero false exact answer.
- Add capability-backed interval or exact local-dimension proof only if a
  measured release failure requires an isolation or existence certificate.
  Finite C2 samples alone are explicitly not such a proof.
