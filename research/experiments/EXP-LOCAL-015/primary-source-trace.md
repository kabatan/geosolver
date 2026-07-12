# EXP-LOCAL-015 primary-source and mechanism trace

Status: pre-outcome research evidence.  This file supplies assumptions and
minimum-success oracles; it does not authorize a performance run or a public
answer.

## Reference / adapted / control separation

| Role | Frozen mechanism | Authority |
|---|---|---|
| `REFERENCE-512-CPQR-H-H2` | fixed 512-bit, five-point `h/h2` CPQR refinement | mechanism diagnostic only; structurally exceeds 600 weighted work at `d=8` |
| `ADAPTIVE-PRECISION-RANK-RESCUE` | condition/rank-triggered 128/256/512-bit CPQR Newton with cross-tier confirmation | experiment candidate; returns a refinement seed only |
| `WEAK-BRACKET-RESCUE` | Float64 complete `4n` rank/projector diagnostic followed by fixed symmetric weak-line probes | experiment candidate; returns sign brackets/refinement seeds only |
| `ISOTROPIC` / `NO-BRACKET` | identical diagnostic and probe work without weak-direction emission authority | mechanism-off controls |
| `E4-EXP-GUARD-SLACK-CPQR` | current frozen local policy | production control |

Every candidate consumes only bounds, scaled residuals, opaque semantic
identity/margins, numerical rank/condition, model agreement and remaining
work.  No case, family, primitive, plugin, target or Gold identifier enters a
candidate interface.

## Adaptive multiprecision full-rank Newton

Primary references:

- Bates, Hauenstein, Sommese and Wampler, *Adaptive Multiprecision Path
  Tracking*, SIAM J. Numer. Anal. 46(2), 2008:
  <https://epubs.siam.org/doi/10.1137/060658862>
- Author manuscript: <https://www3.nd.edu/~jhauenst/preprints/bhswAMP.pdf>
- PHCpack official variable-precision Newton reference:
  <https://homepages.math.uic.edu/~jan/phcpack_doc_html/refman.html>
- Bertini official adaptive-precision endpoint-sharpening manual:
  <https://bertini.nd.edu/BertiniUsersManual.pdf>

The references require an isolated nonsingular solution and choose precision
from conditioning and evaluation-error bounds.  A black-box GeoTarget plugin
usually does not expose the analytic error terms, so the adapted candidate
uses agreement of rank, residual and correction across adjacent precision
tiers.  Rank deficiency at the highest authorized tier is typed unknown, not
success.  Existing independent 512/768-bit canonical replay remains the only
answer authority.

Minimum-success oracle: a rotated system
`A_delta * (x - x_star) = 0`, with a two-by-two block
`[1 1; 1 1+delta]`, `delta=2^-160`, embedded in dimensions 2/4/8.  Float64
loses the perturbation; the candidate must start at 256 bits, detect full rank,
take a nonzero correction, confirm at 512 bits and remain within 600
precision-weighted work.  A stationary nonroot, manifold, missing C2,
semantic change or exhausted complete-stencil reserve must return typed
unknown.

## Rank-revealing weak direction and scalar bracketing

Primary references:

- Zeng, *A Newton's Iteration Converges Quadratically to Nonisolated
  Solutions Too*: <https://arxiv.org/abs/2101.09180>
- NAClab official software index: <https://users.math.msu.edu/users/lit/Software.htm>
- *Estimates on the domain of validity for Lyapunov--Schmidt reduction*:
  <https://arxiv.org/abs/2406.00066>
- Alefeld, Potra and Shi, ACM Algorithm 748:
  <https://doi.org/10.1145/210089.210111>
- SciPy official TOMS 748 interface:
  <https://scipy.github.io/devdocs/reference/generated/scipy.optimize.toms748.html>
- Boost official derivative-free root solvers:
  <https://www.boost.org/doc/libs/release/libs/math/doc/html/math_toolkit/roots_noderiv.html>

Zeng's rank-r Newton requires the correct numerical rank and semiregularity;
it does not make a stationary nonroot into a root.  The current adapted first
stage therefore claims only stable one-dimensional weak-projector evidence and
strict sign brackets.  It does not claim a Lyapunov--Schmidt theorem, root
existence, isolation or completeness.  Bracket endpoints are refinement seeds
for the adaptive-precision and canonical-validation stages.

Minimum-success oracle: a parameterized system with
`F_1=prod(x_1-r_j)` and strong equations `F_i=x_i-phi_i(x_1)`, using 4/8
clustered simple roots and rotated variable/residual replicas.  The candidate
must detect one stable weak dimension and reproduce the same bracket/root class
under signed permutation and orthogonal transforms.  Even/tangent roots,
two-dimensional weak spaces, `g == 0` manifolds, semantic crossings and
unresolved signs are typed unknown.

## Work and causal classification

All callbacks, failed stencils, invalid semantic samples and inner profile
evaluations are charged before invocation as

`callback_cost * ceil(precision_bits / 53)`.

The formal rescue budget is 600 weighted work.  The fixed 512-bit reference
requires at least `(1 + 8d) * 10 = 650` at `d=8` before its first Newton step;
it is therefore classified `BUDGET_OR_PARAMETER_LIMITED`, not a failed
mechanism.  A performance-negative candidate can be called a bounded mechanism
negative only after source conformance, minimum success, complete mechanism
activation, applicability, same-work accounting and independent causal audit
all pass.

## 2026-07-12 current-literature scan

The cycle-start search also found Karapetyants, Kolmogorov and Zapata,
*Computing singular solutions of polynomial systems: towards superlinear
convergence without deflation* (arXiv:2607.06329, submitted 2026-07-07):
<https://arxiv.org/abs/2607.06329>.  Its corank-one Arclength Endgame is a
genuinely different future candidate: it follows a polynomial homotopy curve,
estimates Puiseux exponents and applies a pseudo-arclength corrector using
system and Jacobian evaluations.  The proved result assumes a polynomial
homotopy, an isolated singular target, a rank condition on the augmented
Jacobian and access to path history.  A generic GeoTarget C2 black box supplies
none of the homotopy/path contract, so importing it into this general local
wave would violate applicability rather than fairly test the method.  It is
therefore preregistered only for a later polynomial-capability rescue lane,
with corank-one activation and isolated-root evidence, and is not mixed into
the present adaptive-precision/weak-bracket axis.
