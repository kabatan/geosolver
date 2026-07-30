# Greedy randomized persistent-dual Bregman--Kaczmarz D0

## Hypothesis and causal reopen

The prior semantic Bregman candidate implemented only the Euclidean special
case, so its dual variable and primal point were identical.  Prior greedy
block Kaczmarz also used ordinary damped `J_S^dagger f_S` warm starts.  This
prototype tests a different state transition: a persistent entropy-mirror
dual iterate for source-declared finite boxes, residual-informed randomized
single-row selection, and a one-dimensional Bregman projection of the local
Newton row before unchanged full-system LM polishing.

The causal reopen is therefore the non-Euclidean persistent dual state and
box-feasible primal map, not another block choice or Kaczmarz radius.  It is
derived from Xiao and Yin, *Greedy randomized Bregman-Kaczmarz method for
constrained nonlinear systems of equations*, arXiv:2406.16112, and Gower,
Lorenz, and Winkler, *A Bregman-Kaczmarz method for nonlinear systems of
equations*, arXiv:2303.08549.

## Frozen mechanism

- Normalize only with caller-supplied source bounds/scales.
- On the `3 mod 4` lane, map a finite open box to binary-entropy dual
  coordinates, select among rows whose scale-free residual distance is at
  least 55% of the maximum, and sample up to two with squared-distance
  probability.
- Repair A changed the mathematical proposal after the initial safe but
  gain-free run: independently solve the scalar Bregman row projections,
  trust-cap their dual displacement, residual-weight their mirror average,
  and retain a decaying dual displacement memory.  This prevents saturated
  rows from jumping directly to a box face and lets coupled rows cooperate
  without reducing to a full-space `J^+f` step.
- Accept only strict complete scale-free residual improvement, then use the
  ordinary full-system LM tail with the remaining callback ledger.
- Ordinals 0--2 are untouched baseline lanes.  Thus baseline quota is 75%
  and candidate quota is 25%.
- Unbounded, malformed, nonfinite, or opaque observations fail closed or use
  the byte-identical baseline lane.  Fresh replay alone may emit a root.

No case ID, name, family, truth, target, target count, or prior outcome enters
the candidate.  This is a disposable generated D0; no real adapter, scorer,
shared framework, HP/CAS, or holdout data is used.

## D0 gate

Three generated infinite families cover sparse chains, dense coupling, and a
strict-bound/large-scale chart.  Each has positive, inconsistent negative,
and semantically invalid near-miss roles.  Both arms receive four starts and
the same 22 callbacks per lane.  Tests require exact 75% lane identity,
callback equality, false/loss zero, opaque and unbounded fallback, and
coordinate/residual permutation plus residual-scale solved-set invariance.

Promotion beyond D0 requires gains in at least two families, no loss/false,
and all work/metamorphic checks.  A real connection is not authorized by this
card.

## Frozen D0 disposition

The initial single-row version was safe and active but produced zero
portfolio gains.  Repair A replaced its proposal with the dual-trust
mirror-average/memory mechanism above.  The frozen 108-case rerun produced:

- gains/losses/false: `0/0/0`;
- activation: `108/108`, accepted row projections: `360`;
- callback and 75%-insurance mismatches: `0/0`;
- coordinate/residual permutation and residual-scale metamorphic failures:
  `0/12`.

The candidate arm solved the same positive portfolio cases only because the
three unchanged baseline lanes did; it added no solve in any of the three
families.  This fails the preregistered benefit gate.  Do not connect or tune
this configuration further.  Reopen only for a different mirror geometry or
state that predicts a cross-family benefit before seeing benchmark outcomes.
