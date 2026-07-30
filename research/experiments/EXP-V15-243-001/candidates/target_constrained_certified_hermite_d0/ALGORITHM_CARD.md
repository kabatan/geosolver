# Target-constrained certified Hermite witness — D0

## Hypothesis

Some rejected exact-coordinate attempts contain a valid exact target proposal
even when no full coordinate tuple can be exactified. For an exact QQ system
`f(x)=0`, raw target `tau(x)`, square-free proposed `p(t)`, rational isolating
interval `(a,b)`, and strict polynomial guards, existence can instead be proved
inside the finite algebra

`A = QQ[x,t] / <f, t-tau, p(t)>`.

This hypothesis is deliberately truth-blind. The motivating aggregate is 46
source-valid missing cases, 330 rejected exact-coordinate confirmations over 41
cases, and rejected proposed target-polynomial attempts split as degree 1: 233,
degree 2: 84, degree 4: 14. Those aggregates are not used for routing or tests.

## Mechanism

1. Validate an exact polynomial-only contract, square-freeness, and that `(a,b)`
   isolates exactly one real root of `p`.
2. Compute a grevlex Groebner basis of the target-constrained ideal and reject
   unit or positive-dimensional fibres.
3. Construct the exact standard-monomial basis and rational coordinate
   multiplication matrices.
4. For the raw strict guards plus `t-a>0` and `b-t>0`, compute exact Hermite
   matrices `H_h=(Tr(M_h M_bi M_bj))`.
5. Count a strict conjunction using

   `2^-m * sum_{e in {1,2}^m} signature(H_{product g_i^e_i})`.

   The `sign(g)^2` term excludes zeros, so guard boundaries do not become
   false positives.
6. Emit no coordinates. An independent verifier checks an injective regular
   matrix representation, commutation and closure, all ideal generators,
   every Hermite matrix and exact inertia, and the final positive count.

The construction follows the exact quotient/Hermite and Tarski-query principle
described by Ayyildiz Akoglu and Szanto, while D0 obtains matrices from exact
Groebner reduction instead of approximate-root reconstruction:
https://arxiv.org/abs/2110.10313

## Applicability and caps

- exact QQ polynomial input only;
- proposed univariate square-free target polynomial and rational open isolator;
- strict polynomial guards only;
- target-constrained quotient dimension at most 32, at most 6 variables, 10
  source equations, 4 raw guards, degree at most 10;
- at most 64 Hermite/Tarski queries after adding the two interval guards.

All unsupported or ambiguous inputs fail closed. Canonical source replay remains
mandatory after this witness is integrated; D0 does not implement that bridge.

## Generated D0 families

- regular zero-dimensional, degree-2 target;
- nonradical/singular, degree-1 target;
- positive-dimensional overall but finite target fibre, degree-4 target;
- no-root interval, wrong-sign strict guard, guard-boundary zero,
  non-square-free target polynomial, positive-dimensional target fibre, and
  inconsistent fibre negatives;
- variable/equation/guard permutation and invertible affine target transforms;
- digest, multiplication-matrix, and Hermite-matrix certificate mutations.

## Gate and decision

D0 advances only if all three positive families and their metamorphs verify,
all negatives fail with the expected category, all certificate mutations are
rejected, and no positive run uses coordinate exactification. Source
applicability remains a separate HOLD until strict predicate semantics plus a
target proposal/isolator producer are connected.
