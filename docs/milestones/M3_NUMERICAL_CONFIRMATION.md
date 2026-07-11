# M3 numerical confirmation checkpoint

Status: numerical gate complete; optional exact backend Phase B remains open

Date: 2026-07-12

Implementation: `c79f0df`

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
- GeoTargetExact package: 103/103 tests green.
- Independent owned-PSLQ probe: `x^d-p` for `d = 2,3,4,5,6,8,10,12` and
  `p = 2,3`, with identical relations at the base and `+256`-bit precisions.

## Source checksums at the implementation checkpoint

| File | SHA-256 |
|---|---|
| `julia/GeoTargetCore/src/high_precision_refinement.jl` | `e1839b6996656aea7c63275aa51d88cd159bc7563bef3a4cdd83aa639b282c96` |
| `julia/GeoTargetCore/src/candidate_validation.jl` | `5cd036667feb36d9b6ffdc5a335ae0cddebe415d2c47a64d20386e5a6d35bcf6` |
| `julia/GeoTargetCore/src/solver.jl` | `0564f8acc75350ebce7c1be8a87629204a0ff105bb59da345aba543460be4cbe` |
| `julia/GeoTargetExact/src/pslq.jl` | `db1ea954f916641a3113031cd9bd05a09817bb89f56722ee6afe8ae0c981cbcb` |

## Remaining M3 work

The optional Phase-B backend must still provide the one-way dependency
`GeoTargetBase <- GeoTargetCore <- GeoTargetExact`, arbitrary-precision shared
sampling, exact reconstruction of every free variable, original-graph C3A
replay, certificate construction and a verifier that reconstructs and
re-substitutes without trusting the PSLQ trace. Until then, nonconstant
`ExactAnswer` promotion remains unavailable by design.
