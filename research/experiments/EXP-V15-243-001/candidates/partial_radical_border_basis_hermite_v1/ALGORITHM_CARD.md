# PARTIAL_RADICAL_BORDER_BASIS_HERMITE_V1

Status before results: `FROZEN_DISPOSABLE_D0`.

## Hypothesis and exact theorem boundary

An approximate cluster need not contain every complex root of the complete
source ideal.  It proposes an exact rational extended moment matrix only.  The
candidate grants authority after exact checks construct a radical
zero-dimensional border-basis ideal `J` satisfying `I subset J`, hence
`V(J) subset V(I)`.  It proves existence of a real root of `J` in an inscribed
ball of the proposal box, on the proposed target fibre, and satisfying the
complete predicate ledger.  It never claims `J=I` or target-set completeness.

The exact checks are: flat full rank of `H_B` and `H+`; a power-monomial basis
connected to one; exact border multiplication matrices; commutation; a
square-free separating characteristic polynomial; every complete source and
target-fibre equality vanishing on the matrices; exact trace-moment
consistency; and exact Hermite/Tarski conjunction count greater than zero.

## Caps frozen before D0/source activation

- variables: 8;
- cluster/quotient dimension: 8, with no duplicate or padded points;
- source equalities: 16; complete-ledger flag mandatory;
- source predicates: 12; complete-ledger and accounting mandatory;
- polynomial total degree: 6; terms: 160;
- target descriptor degree: 4, primitive/square-free/irreducible;
- coordinate magnitude: 128;
- input precision: 53--256 bits;
- rational reconstruction denominator: 4096;
- absolute reconstruction error: strictly below `2^-30`;
- saved-proposal geometric dedup radius: `2^-14 * max(1, ||z||_inf)`;
- saved proposal box half-width: `2^-9 * max(1, |z_i|)` per coordinate;
- expanded Hermite/Tarski query terms: 4096;
- fixed separator coefficient panels: `(1,2,4,...)`, `(1,3,9,...)`, and
  `(1,5,11,...)` truncated to the variable count.

No cap may be changed from generated or saved-proposal results.  Failure of
rational moment reconstruction, including a non-Galois-stable real-only
cluster, fails closed.  No root is added, duplicated, conjugated, or padded.

## Scope and non-overlap

The candidate is private disposable Python.  It does not compute a Groebner
basis, resultant, RUR/LUR, coordinate minimal polynomial, or complete source
quotient.  Approximate roots only propose exact moments; exact matrix
identities carry authority.  Raw source recompilation and canonical replay
remain mandatory for any later connector.  D0/source gate outputs have
`completeness=false` and do not enter a formal scorer.

Primary basis:

- https://arxiv.org/abs/2110.10313, especially Algorithm 4.1 and the proof of
  Theorem 4.2 before its dimension-equality step.
- https://arxiv.org/abs/1102.4681 is a negative comparison: its LUR algorithm
  begins with the complete Groebner quotient and isolates every root.
