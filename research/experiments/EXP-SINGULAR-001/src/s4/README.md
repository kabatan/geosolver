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
- The candidate may accept only `CandidateInput` and common controls. The
  candidate's `EndpointOracle.analytic_jacobian` is `nothing`; analytic
  Jacobian and Hessian-direction fixtures stay in `S4DevelopmentCase` and are
  available only to the separately coded control.
- Candidate/control numerical helpers may not be shared. Only the work ledger,
  canonical semantic replay types, frozen input/counter data and final artifact
  predicates are common.
- Both maps must keep `U2`, `V2` and `v` from `J(x)` through the range and null
  steps. A decomposition at `x_range` is a protocol violation.
- A2 audit probes are different from iteration probes: each trajectory fixes a
  physical `v_ref` from its 256-bit start reference and transports it into every
  ell=65 start/final precision/radius basis before comparing B spectra or final
  corrections. Step-safety ell=1 and actual ell=1:64 steps retain local probes.
- Every trajectory, precision and confirmation consumes the same endpoint-wide
  64-iteration/4,096-callback ledger for its variant.

The next legal state transition is input materialization and an input-freeze
commit. Until then no `run_s4` symbol is allowed.
