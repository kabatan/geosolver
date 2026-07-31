# EFFECTIVE_HEIGHT_SEPARATION_TARGET_CERTIFICATE

## Hypothesis

For a digest-bound exact local source root, suppose every coordinate already
has a primitive irreducible integer minimal polynomial and an exact real-root
isolator.  For an untrusted target descriptor `p`, interval evaluation gives an
upper bound `U` on `|p(raw_target)|`.  Coordinate degree and height bounds give
a computable lower bound `L>0` for the same value if it is nonzero.  Therefore
`U < L` proves exact zero without Gröbner ideal membership.

Repo audit found no implementation of this mechanism.  The nearest earlier
card named a global degree/height contract only as an unimplemented reopen
condition.

## Sound bound used by the prototype

Let coordinate `alpha_i` have primitive irreducible minimal polynomial `q_i`
and let `M_i` be the coefficient L1 norm of `q_i`.  Mahler measure gives

```text
h(alpha_i) <= log(M_i).
```

The joint field degree is at most `D = product degree(q_i)`.  Expand
`p(raw_target) = G(alpha_1,...,alpha_n) / Q`, with integer `G` and positive
integer `Q`.  For `N` monomials, repeated use of
`h(a+b) <= h(a)+h(b)+log(2)` and `h(ab) <= h(a)+h(b)` gives

```text
B = Q * 2^(N-1)
      * product_over_terms(|coefficient|_+ * product_i M_i^exponent_i)
h(p(raw_target)) <= log(B).
```

If the value `beta` were nonzero, its minimal polynomial constant term and the
product over conjugates imply `|beta| >= exp(-deg(beta) h(beta))`.  Hence

```text
|p(raw_target)| >= B^(-D).
```

The prototype accepts only when a rational interval enclosure satisfies the
strict opposite inequality.  It recomputes degree, irreducibility, coefficient
L1 norms, isolators, ordinals, `B`, and `D`; caller-supplied underestimated
height metadata is rejected.

## Authority boundary

- Source, endpoint bits, obligation ledger, lineage, coordinate facts, and
  serialized QQBar records are digest-bound.
- The upstream certificate must prove one same-endpoint source root, all exact
  equations, guards, branches, and same-root coordinate facts.
- The raw target is the source-bound rational polynomial; its full interval
  must lie in the descriptor isolator.
- Numeric proximity is never equality.
- Output is always `authority=false`, `target_release=false`; final unchanged
  canonical source replay is mandatory.

## D0 result

Generated D0 passed **11/11**, with five positives across affine, triangular,
coupled, permutation, and scale structures.  Six negatives cover a nonzero
rational perturbation, wrong factor, underestimated height, singular source,
failed branch replay, and wrong ordinal.  False accepts: **0**.

Next gate is a truth-blind static census of already stored exact coordinate
facts.  The mechanism is useful only when their isolators are narrow enough to
beat the conservative `B^-D` threshold and the old exact target link is absent
or fails.
