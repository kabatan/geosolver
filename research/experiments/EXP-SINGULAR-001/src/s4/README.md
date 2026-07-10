# S4 private source boundary

This directory is a sequencing guard, not a product package.

- Input definitions and manifest construction live in the parent
  `s4_inputs.jl` so they can be frozen before an algorithm exists.
- The input manifest omits Gold configurations/targets and only binds the hash
  of a separate analysis artifact. Candidate code receives neither artifact.
- `candidate.jl` and `analytic_control.jl` must not be added until the committed
  `s4-input-freeze.json` names their parent manifest hash.
- The input freeze must bind the preregistration, final A1, A2, generator
  scaffold commit/source and current manifest-builder source hashes.
- The candidate and control accept only `S4CandidateInput`, whose
  `S4BlackBoxOracle` physically has no id, family, metamorphic group, Gold,
  generator parameter, analytic Jacobian, or Hessian fixture field. Analytic
  Jacobian and Hessian-direction fixtures stay in `S4DevelopmentCase` and are
  passed separately only to the independently coded control.
- Candidate/control numerical helpers may not be shared. Only the work ledger,
  canonical semantic replay types, frozen input/counter data and final artifact
  predicates are common.
- Both maps must keep `U2`, `V2` and `v` from `J(x)` through the range and null
  steps. A decomposition at `x_range` is a protocol violation.
- A2 audit probes are different from iteration probes: each trajectory fixes a
  physical `v_ref` from its 256-bit start reference and transports it into every
  ell=65 start/final precision/radius basis before comparing B spectra or final
  corrections. Step-safety ell=1 and actual ell=1:64 steps retain local probes.
- The primary endpoint selects the frozen nullity. A trajectory start inherits
  that route and does not redetect it from its temporary perturbation gap;
  every final audit does repeat the strict smallest-gap selection and must
  recover the frozen nullity.
- Every trajectory, precision and confirmation consumes the same endpoint-wide
  64-iteration/4,096-callback ledger for its variant.

Development inputs were frozen at commit `3fb7480`. A3/A4 preceded mechanism
execution; A5 binds corrections found only on family-disjoint synthetic
fixtures. Static tests reconstruct the already-frozen input/Gold documents,
but no development mechanism outcome has been executed or assessed against
Gold. The next legal transition is an implementation-freeze commit. The
36-case development split remains forbidden until that freeze exists and
verifies exactly.
