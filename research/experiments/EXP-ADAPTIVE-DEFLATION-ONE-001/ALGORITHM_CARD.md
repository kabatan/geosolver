# EXP-ADAPTIVE-DEFLATION-ONE-001

Status: D0 proposal-only survivor; no solver connection and no emission authority.

Hypothesis: a corank-one two-step Newton proposal should begin at low precision
and escalate only when rank/projector, endpoint, or canonical residual evidence
disagrees.  This can recover ill-scaled singular proposals without paying fixed
high precision on every endpoint.  The prototype is intentionally limited to
normalized square real 2x2 C2 callbacks and is not a general singular solver.

Mechanism: the range/null split and projected Hessian step follow Lee--Li--Zhi
([arXiv:2305.10803](https://arxiv.org/abs/2305.10803)).  Precision rungs are
64/96/144/216/324 bits, motivated by reactive adaptive multiprecision
([SIAM JNA 46(2)](https://doi.org/10.1137/060658862)).  Adjacent successful
rungs must agree in both left/right null projectors and normalized endpoint;
an independent 384-bit residual replay is proposal evidence.  All callback
work is charged by bits/64 and the route has a hard 256-callback cap.

Past/reopen audit: `NEG-014` found fixed 128/256-bit S4 at 11/15 with four
orthogonal-representation failures.  `EXP-SINGULAR-002` later proved that no
finite C2 transcript, including higher precision and tensor spectra, certifies
local isolation.  Therefore this arm never promotes or emits a target.  It may
only add a start to a <=25% side quota; the existing proof-bearing exact
coordinate/source/guard/branch/target verifier remains the sole authority.
This is distinct from `EXP-DEF-001`, which deflated away from already known
regular roots to find a different root.

D0 after one mathematical repair (separating the normalized near-singular
window from arithmetic uncertainty): 220 generated cases, comprising three
unrelated deflation-one families, orthogonal/signed representations, and 100
higher-depth/manifold/close-regular/inconsistent/opaque controls.  Adaptive
proposal success was 110/120 versus fixed-256 100/120 and fixed-64 30/120;
adaptive versus fixed-256 was +10/-0.  Negative-control proposals, false final
emissions, and opaque mismatches were all zero.  Mean precision-equivalent work
was 1.213x fixed-256, so this is recall evidence, not speed evidence.  Six unit
and metamorphic checks passed.

Reopen/next gate: connect only as proposal-only side starts with at least 75%
of the frozen baseline untouched.  Require source-only activation, deadline,
opaque fallback, and then truth-blind D1.  Any direct singular-root promotion,
or any dependence on case/family/Gold, terminates the arm.
