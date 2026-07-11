# GeoTargetExact

Optional exact-algebraic backend for GeoTarget. This directory has its own
environment so Nemo/FLINT are not dependencies of the default numerical solver.

Phase A contains:

- an exact `AlgebraicReal <: Real` wrapper over Nemo `QQBar`;
- bounded rational reconstruction;
- the degree/height/precision recognition ladder;
- Nemo's heuristic LLL integer-relation comparator;
- primitive/irreducible factor selection and exact real-root isolation;
- fail-closed certificate descriptor reconstruction.

Nemo 0.56.1 does not expose PSLQ. The implemented relation generator is named
`nemo_lll_relation` in code and evidence and must not be reported as PSLQ.
Recognition only proposes a candidate; it never establishes an `ExactAnswer`.
Core integration and original-graph C3A substitution intentionally return a
typed unsupported result until Phase B.

Run the isolated suite with:

```sh
julia --startup-file=no --history-file=no --project=julia/GeoTargetExact \
  -e 'using Pkg; Pkg.test()'
```
