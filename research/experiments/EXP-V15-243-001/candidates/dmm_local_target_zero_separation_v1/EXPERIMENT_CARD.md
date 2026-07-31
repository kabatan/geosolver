# DMM_LOCAL_TARGET_ZERO_SEPARATION — source/precision static gate

## Mechanism and theorem ledger

For a square exact integer source system `F(x)=0`, a certified regular local
root box, exact raw target `T(x)`, and untrusted primitive descriptor `p`, form

```text
q(x) = p(T(x))
Sigma_q = { F_i(z+s)=0, m-q(z+s)=0 }.
```

The integer shift `s` is chosen mechanically from the certified rational box so
every selected `z_i=x_i-s_i` excludes zero.  In the contradiction branch
`q(x) != 0`, `m` is also nonzero.  The source Krawczyk certificate proves a
regular isolated root; the augmented Jacobian is block triangular with the
same nonsingular source block.  Hence the selected augmented root is an
isolated toric root to which DMM applies.

The bound ledger follows Emiris, Mourrain, and Tsigaridas, *The DMM bound:
multivariate (aggregate) separation bounds*, Theorem 11 and Eqs. (20), (23)
([arXiv:1005.5610](https://arxiv.org/abs/1005.5610)).  For augmented dimension
`N`, Newton supports, mixed-volume bounds `M_i`, `M_0`, coefficient infinity
norms, and coefficient bitsize `tau`, the implementation would record every
input to

```text
rho = product_i (#Q_i)^M_i
C   = product_i ||f_i||_infinity^M_i
A   = product_i sqrt(M_i) * 2^M_i
L20 = (2^M0 * rho * C * A)^(-1)

E23 = d^N + N*(tau + N*log2(d) + 2)*d^(N-1)
      - ((N^2-N)/2)*log2(d)
L23 = 2^(-ceil(E23))
```

Eq. (20) supplies the sparse-support lower bound (with the Theorem-11 `A`
factor for excess components); Eq. (23) supplies the looser dense fallback.
If a rational interval evaluation gives `U >= |q(x)|` and
`U < max(L20,L23)`, the nonzero contradiction is impossible, so `q(x)=0`.
No resultant is constructed.  The descriptor isolator/ordinal and final
unchanged canonical source replay remain separate mandatory joins.

## Required provenance and assumptions

- `q=p(raw_target)` must be constructed from the raw source-bound target and a
  fully validated untrusted descriptor; no numeric target substitution.
- Every source equation, guard, definedness/branch obligation, Krawczyk box,
  source bytes, endpoint bits, and lineage must be digest-bound.
- Coefficients must be exact integers after constant denominator clearing.
  Algebraic constants need explicit polynomial lifts and branch obligations;
  they are not rounded into the integer system.
- The torus shift must be integral, invertible, source-independent except for
  the certified box, and included when recomputing supports, degree, norms, and
  bitsize.
- Mixed volumes/support cardinalities and the Eq. (20)/(23) ledger are
  recomputed; caller-supplied estimates cannot reduce the bound exponent.
- Output remains local, `authority=false`, and makes no target-set completeness
  claim.

## Static census and decision

The read-only artifact inventory found 17 verified Krawczyk certificates over
8 unique sources and 8 truth-blind structural signatures.  Only 3 sources
also carry both an untrusted target polynomial and exact raw-target provenance;
the other 5 source-certificate jobs deliberately never read a target.  Those 3
integer systems are torus-shiftable, but all already have an exact ideal link.

The preregistered gate requires at least 4 sources across 2 signatures before
computing the expensive precision ledger.  Observed: **3 sources / 3
signatures**, so the gate fails.  Eq. (20)/(23) precision evaluation and D0 are
not run, and no cap/radius tuning or post-hoc target injection is allowed.

Decision: **STATIC STOP** and pivot to a mathematically distinct exact-authority
mechanism.
