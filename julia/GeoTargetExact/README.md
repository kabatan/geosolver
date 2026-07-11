# GeoTargetExact

Optional exact-algebraic backend for GeoTarget. This directory has its own
environment so Nemo/FLINT are not dependencies of the default numerical solver.

The backend contains:

- an exact `AlgebraicReal <: Real` wrapper over Nemo `QQBar`;
- bounded rational reconstruction;
- the degree/height/precision recognition ladder;
- an owned Ferguson-Bailey-Arno PSLQ candidate generator;
- Nemo's heuristic LLL integer-relation diagnostic comparator;
- primitive/irreducible factor selection and exact real-root isolation;
- all-free-variable recognition through Core-owned dual-precision samples;
- an original-`ProblemSpecV1` C3A interpreter with exact bounds, relations,
  guards, domains, branch margins, branch identity, and target replay;
- canonical configuration/target artifacts and independent reconstruction;
- a concrete `NemoExactBackend <: AbstractExactBackend` that self-verifies
  every `ExactAnswer` before returning it.

Nemo 0.56.1 does not expose PSLQ. Production recognition therefore uses the
owned `pslq_relation` implementation and records `owned_pslq_v1`. The separate
`nemo_lll_relation` routine is diagnostic-only and must not be reported as PSLQ.
Recognition only proposes a candidate. Acceptance additionally requires every
free variable to reconstruct at both requested precisions and the original
graph to pass exact C3A replay.

Each operation on an exact path must advertise `C3A` and provide an explicit
`algebraic_prover`; numerical evaluators and relation `truth` callbacks are not
used as proof callbacks. A relation prover returns its exact algebraic residual,
which must equal zero. Bounds and non-strict margins allow equality, while
strict guard/domain and both selected-branch margins must be positive. Branch
keys must match the numerically confirmed branch signature.

Integer and rational scalar literals are exact. Finite floating-point scalar
literals are embedded as their exact binary rationals. Structured literals or
callback values containing floating-point leaves are unsupported and fail
closed. The verifier distrusts certificate payloads: it reconstructs every
algebraic descriptor and independently replays the supplied original graph.

Run the isolated suite with:

```sh
julia --startup-file=no --history-file=no --project=julia/GeoTargetExact \
  -e 'using Pkg; Pkg.test()'
```
