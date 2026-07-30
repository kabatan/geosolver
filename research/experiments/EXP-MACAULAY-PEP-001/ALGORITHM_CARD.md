# EXP-MACAULAY-PEP-001 — rank-completing Macaulay-nullspace proposal D0

## Status

`GO_PROPOSAL_PROTOTYPE_ONLY`

This is a disposable generated-case D0, not a solver connection, source
coverage claim, exact authority, or completeness claim.

## Mandatory overlap audit and reopen gate

The archive contains a direct neighboring STOP:
`wave18_numeric_macaulay_action_g0`.  It proposed a general small rational-
polynomial source compiler, floating Macaulay nullspace, quotient action
matrices, joint eigendecomposition, and source replay.  Its four eligible
development sources were singleton signatures; it stopped before code because
the finite quotient algebra was already represented by RUR/Groebner/FGLM/
Wiedemann routes.  `eligible_polynomial_homotopy_revisit` and the homotopy/
monodromy ledgers independently close path-tracker backend and schedule changes.

The present owner-directed reopen is deliberately narrower and causal:

- it is unavailable without a source-derived `stable_rank_deficient` or
  `near_multiple` signal;
- it targets defective/nilpotent multiplication pencils near multiple roots,
  not ordinary polynomial branch enumeration;
- it uses a deterministic rank-one completion of that defective pencil and
  exposes only replay-accepted numerical proposals;
- regular-rank, positive-dimensional, high-degree, opaque, and nonpolynomial
  inputs return immediately to the baseline;
- at least 75% of portfolio slots remain baseline work.

Thus this does **not** reopen generic homotopy, change a path order, or claim
that a new Macaulay backend improves the four archived regular sources.  If a
future source-native census cannot find repeated anonymous rank-deficient or
near-multiple structures, or if rank-one completion is neutral against the
same Macaulay pencil without completion, the lane returns to the prior STOP.
Threshold, basis ordering, precision, and Macaulay degree tuning alone are not
future reopen gates.

## Mechanism

For a square literal-polynomial block of at most two variables, degree at most
three, and Bezout quotient dimension at most eight:

1. Construct the degree-of-regularity Macaulay relation matrix.
2. Require its observed numerical nullity to equal the structural Bezout
   dimension.  A mismatch rejects positive-dimensional and rank-ambiguous
   systems instead of inferring a convenient dimension.
3. Select a quotient basis from low-degree nullspace rows by CPQR and construct
   commuting coordinate multiplication matrices.
4. Form a deterministic generic coordinate pencil and add a fixed rank-one
   completion to split defective multiple-root eigenstructure.
5. Project finite nearly-real eigenvectors to coordinates, enforce literal
   bounds, and pass every point to the caller's untouched canonical replay.
6. Emit only replay records with `safe=true` and residual at most `1e-7`.

The rank-one-completed pencil is only a proposal generator.  It cannot release
an exact descriptor or bypass source/guard/branch semantics.

## Research basis

- Batselier, Dreesen, and De Moor,
  [On the null spaces of the Macaulay matrix](https://doi.org/10.1016/j.laa.2014.07.035),
  relates Macaulay right nullspaces, multiplication structure, and roots.
- Govindarajan et al.,
  [A Fast Algorithm for Computing Macaulay Null Spaces of Bivariate Polynomial Systems](https://doi.org/10.1137/23M1550414),
  treats numerical right-nullspace computation for approximate common roots.
- Hochstenbach, Mehl, and Plestenjak,
  [Solving singular generalized eigenvalue problems by a rank-completing perturbation](https://arxiv.org/abs/1805.07657),
  motivates rank completion rather than treating a singular pencil as regular.
- Hochstenbach, Mehl, and Plestenjak,
  [Numerical methods for eigenvalues of singular polynomial eigenvalue problems](https://arxiv.org/abs/2406.16832),
  extends rank-completion/projection/augmentation ideas to singular PEPs and
  includes bivariate polynomial-system applications.

No theorem from these papers is used to claim all-root recall or a certificate.

## Generated D0 evidence

Seventeen short tests passed on physical core 15.

- Positive families: univariate repeated-plus-simple root, a separable double
  root, and a nilpotent cusp block.
- Negative families: positive-dimensional common factor, complex-only real
  search, and inconsistent parallel quadratics.
- Near misses: near-colliding distinct roots, regular-rank polynomial, degree-
  four block, and opaque transcendental block.
- Additional gates cover canonical-replay veto and exception fallback,
  equation/variable permutation, deterministic completion, baseline 75% quota,
  and proposal-only authority.

No benchmark source, target truth, scorer, development result, validation, or
sealed artifact was read or executed.  The known locations/names in the overlap
ledger were inspected only to classify mechanism duplication.

## Frozen hashes

- Candidate: `d8a2992931ba94c58c98928325a777997164311c5192b809e8c2f0a029187312`
- Generated cases: `8210987a44a5500f82df18ed6e207e1ec79c4fe0078803df8a612a76973ff54c`
- Tests: `f186011bb16e1cfbd3fb36f99753340a728879c283620a825ad0a85e8f981650`
