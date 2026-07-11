# GeoTargetExact

Optional exact-algebraic backend for GeoTarget. This directory has its own
environment so Nemo/FLINT are not dependencies of the default numerical solver.

Phase A contains:

- an exact `AlgebraicReal <: Real` wrapper over Nemo `QQBar`;
- bounded rational reconstruction;
- the degree/height/precision recognition ladder;
- an owned Ferguson-Bailey-Arno PSLQ candidate generator;
- Nemo's heuristic LLL integer-relation diagnostic comparator;
- primitive/irreducible factor selection and exact real-root isolation;
- fail-closed certificate descriptor reconstruction.

Nemo 0.56.1 does not expose PSLQ. Production recognition therefore uses the
owned `pslq_relation` implementation and records `owned_pslq_v1`. The separate
`nemo_lll_relation` routine is diagnostic-only and must not be reported as PSLQ.
Recognition only proposes a candidate; it never establishes an `ExactAnswer`.
Core integration and original-graph C3A substitution intentionally return a
typed unsupported result until Phase B.

Run the isolated suite with:

```sh
julia --startup-file=no --history-file=no --project=julia/GeoTargetExact \
  -e 'using Pkg; Pkg.test()'
```
