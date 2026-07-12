# Simplicial star emitter — mechanism note

Status: experiment-local implementation, pre-corpus and non-production
Source: `src/simplicial_star_emitter.jl`
Test: `test/stage_next_simplicial_star.jl`

## Mechanism and authority boundary

This is a symmetric-star-cover proposal heuristic inspired by simplicial sampling in
SHGO. It is not full SHGO, a selected cube triangulation, a homology computation, or
an implementation to which SHGO isolation or global-optimization theorems transfer.
The normalized base consists of all `2^d` cube corners plus the center. Symmetric
center/corner/adjacent-corner simplices supply adjacency and incident-star geometry.

Every base vertex is prescored with the bounded scaled-residual score. The guided arm
finds branch-compatible combinatorial minimum vertices and proposes points halfway
between such a vertex and barycenters of its incident simplices. The unguided arm uses
the same base and incidence universe, but selects refinement geometry without reading
scores. Complete signed-permutation-invariant geometry shells are atomic: a shell that
does not fit the finite cap is not split.

These labels and points are proposal evidence only. No finite set of vertices,
adjacency pattern, missing minimum, positive score, or invalid region establishes root
isolation, root absence, local dimension, target completeness, or configuration
completeness. The report explicitly has no answer, homology, or completeness authority.

## Applicability and 48-screen accounting

The module requires a finite nondegenerate box, the frozen `8eps(Float64)`
normalization-resolution gate, `2^d + 1 <= 48`, and fixed simplex/incidence memory
caps. Dimension six and above is therefore typed inapplicable and performs no emitter
callbacks.

`plan_simplicial_pair` physically evaluates the identical base vertices once and
shares those observations between the paired arms. For comparison accounting, each
arm is nevertheless charged its full base prescores. Refinements are then physically
evaluated separately by arm. Returned base proposal points are deep-copied per arm;
mutating one plan cannot mutate the paired plan or the internal base records.

`shared_base_evaluation=true` describes this applicable paired construction only;
typed inapplicable plans set it to false. `all_prescores_returned` means that every
prescore performed inside the module has a returned proposal record. It does not claim
that a fallback was generated or that any point received local-solver service.

Each arm owns exactly 48 logical screening slots:

```text
base prescores + arm refinement prescores + typed IID fallback requests = 48
```

The module does not invent the fallback points. Accounting is complete only when the
experiment runner generates each typed fallback from the frozen fresh-IID namespace,
prescores it, and passes it to the same frozen local solver and canonical service as
every emitter proposal. Until that happens, the module result alone is not an
equal-work efficacy trial.

The module report is not physical callback-count authority. The experiment runner's
raw ledger must independently count the one shared physical base pass, both arms'
physical refinements, every fresh-IID fallback prescore, and subsequent local work,
then reconcile those observations with the two 48-slot logical accounts.

Guided and unguided refinement counts are intentionally independent. A missing or
small guided minimum star must not truncate the geometry-only control. Equality is
required for total logical screens and later local-attempt service, not for the number
of emitter-generated refinements; arm-specific IID fallbacks close the difference.

With only 48 slots, complete symmetry orbits may not fit after the base. In particular,
dimensions four and five can legitimately produce zero refinements and return all
remaining slots as IID fallbacks. This is a predefined general high-dimensional break
condition, not evidence of an empty domain and not grounds for post-outcome exclusion.

## Truth and representation boundaries

- Bounds are normalized before geometry selection; under-resolved affine scales are
  typed inapplicable. This does not prove invariance to arbitrary residual rescaling;
  the adapter still relies on declared row scaling.
- Signed coordinate permutations preserve selected proposal multisets by admitting
  only complete invariant shells. Orthogonal rotations are not symmetry claims for
  this axis-aligned construction.
- Branch tokens are opaque. Only conservative equality is used for local-minimum
  adjacency; token names, order, hashes, and target meaning are unavailable.
- Invalid, nonfinite, throwing, malformed, and branch-missing observations receive
  score one and remain serviced proposals. An invalid vertex is not treated as a
  proof that its neighborhood is invalid.
- The implementation receives no case, family, file, primitive or plugin name, Gold
  target, known root, target identity, or external optimizer success/minimum.
- Duplicate proposals are not suppressed, and no configuration or target evidence is
  irreversibly merged.

## T0 kill gate

The candidate is killed before promotion if any callback is unaccounted, any evaluated
point is not serviced, IID fallback is not fresh/prescored/locally serviced, or any
answer/truth/completeness authority leaks into the emitter. It is also killed if scale
or signed-permutation replicas change the eventual answer class, if guided selection
does not beat both the independent unguided control and prescored D0 at equal total
callback work, if signal is confined to MultiRoot/Tangent or one family, or if no
terminal new-target signal appears in unrelated families. The dimension-four/five
zero-refinement regime and construction overhead must be reported, not hidden by a
case-specific applicability rule.
