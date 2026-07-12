# EXP-LOCAL-011 — h/h2 full-rank SVD endpoint correction

Status: **implementation and T0 preregistration frozen; no outcome run**

This experiment isolates endpoint correction from local globalization. Every
variant starts with the unchanged `prod-tol-120x600` LM-QR trajectory. Only a
finite, in-box, semantics-valid base endpoint with declared-scale residual
`<= 1e-12` is probed. Other base endpoints pass through without another
callback.

`E2-FD2-SVD3` builds second-order `h` and `h/2` Jacobians in normalized box
coordinates, adds a floating-point rounding envelope to their disagreement,
and requires full column rank by `sigma_min > 2 eta`. It solves both linear
least-squares systems with full-rank SVD (no truncation), requires
`max(||p_h||_2, ||p_h2||_2, ||p_h-p_h2||_2) <= 1e-6`, and performs at most
three real Armijo corrections followed by reproof. If no correction is taken,
the current proof is already the final proof and is reused. A semantics-invalid FD or
Newton sample makes the result unknown; unknown qualified endpoints are
dropped. The solver-lab case exposes aggregate semantics validity but no branch
identity, so this T0 makes no branch-signature claim; production canonical
replay remains authoritative for branch stability.

The paired `E2-FD2-SVD3-SHADOW` executes the identical probe/correction
trajectory but returns the original LM endpoint. It isolates endpoint choice
from the extra callback work. The common wave runner and aggregation are owned
outside this directory; this experiment contains no outcome artifact.

[`preregistration.json`](preregistration.json) freezes the representative
9-case, maximum 64-start T0, callback-prefix authority, promotion gate, and
kill conditions. [`test/runtests.jl`](test/runtests.jl) covers regular roots,
singular/manifold rejection, strict-boundary behavior, row scaling, signed
permutation, callback identity, and zero-probe pass-through.
