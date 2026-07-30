# Mechanism overlap audit

## Search scope

`rg` covered the extracted archive's 551 candidate directories and 1,278
card/decision/ledger files, plus the current coefficient-monodromy,
local-monodromy, ED/moved-slice, and adaptive-deflation worktrees.  Exact terms
`exceptional stratum`, `exceptional set`, `fibre/fiber product`, `dimension
jump`, parameter/coefficient perturbation, monodromy, moved slice, and
deflation were searched.  No implemented archive candidate forms replicated
source-family fibres to infer a nearest exceptional parameter stratum.

## Nearest mechanisms and material differences

| lineage | state and operation | failure attacked | difference here |
|---|---|---|---|
| coefficient/regular-root return monodromy | one accepted regular root; lift a closed coefficient/residual loop and read its sheet permutation | missing root in a regular covering | this lane uses an open uncertainty ball, no loop or permutation, and selects a structure-changing parameter by same-parameter replicated fibres |
| local monodromy orbit ledger | a rank-deficient source germ; move a generic local slice around the germ and group witness permutations | collapsed local branches/components | this lane works in external source-parameter space and compares whole fibres across parameters; it does not infer local irreducible components |
| ED-critical moved slice | a positive-dimensional source set at fixed source data; ED projection and complementary affine slices | sparse sampling of an existing source manifold | this lane changes source parameters temporarily to locate a nearby exceptional locus, then returns to the original source |
| deflation-one / isosingular lines | fixed source residual plus range/nullspace, second derivative, or auxiliary multiplier equations | slow convergence to a singular isolated root | this lane does not deflate or augment the source system and also covers count/dimension jumps without assigning multiplicity authority |
| certified polynomial homotopy | solve an eligible polynomial source from a generic start system | global isolated-root enumeration | this lane is local to an unstable cluster and requires a nearby structure change; it neither tracks all paths nor claims completeness |
| naive perturb-and-resolve / residual continuation | perturb residual/parameter for conditioning or use an open path, then retry | bad basin or ill-conditioning | this lane reopens perturbation only behind replicated-fibre coincidence/rank/count evidence and ranks fibres relative to an inferred exceptional stratum |

## Reopen gate

Blind perturb-and-resolve remains closed.  The gate reopened here is the new
observable state absent from those attempts:

- at least two endpoints share the same perturbed parameter and nearly
  coincide, or the fibre rank/cardinality changes;
- the signal occurs inside a source-scaled uncertainty ball around an already
  unstable cluster;
- perturbed endpoints are continued back and independently replayed against
  the original source;
- ordinary search retains at least 75% of the starts.

Changing radius, sample count, solver backend, or continuation steps alone is
not a reopen condition.  Without replicated-fibre structural evidence, the
candidate falls back instead of degenerating to naive perturbation.
