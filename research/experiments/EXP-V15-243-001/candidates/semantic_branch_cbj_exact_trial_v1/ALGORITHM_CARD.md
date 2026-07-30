# SEMANTIC_BRANCH_CBJ_EXACT_TRIAL_V1 — source eligibility

## Decision

**Static source gate: FAIL. Runtime/D0 and connector: STOP.**

Mechanism hash: `231e1d21dd1efd30338af3db55f9c94c61f620fd00aff74f875061068219330d`.

The source scan found four structurally ready attempts with four anonymous
hashes. Every ready attempt has two independent binary branch variables and
four full assignments, so the basic reach requirement passes. However, only
one attempt on one hash has at least two source-exact strict guard/segment atoms
with the same complete branch-key dependency subset. The unchanged recurrent
conflict requirement is `2 attempts / 2 hashes`; therefore the combined gate
fails.

The retained count is static potential, not observed conflict evidence. The
eligible real surface in this census contains only typed line-circle
`Intersect(..., exclude=point)` variables with syntactically proved
common-point incidence.
The bounded periodic-sheet and restricted bounded scalar two-root recognizers
are present but contribute no ready real attempt. Tangent/ambiguous selectors,
implicit or dynamic selection, unproved exclusion incidence, overlapping
scalar branch models, and products above 16 fail closed.

## Candidate contract if reopened

- Enumerate complete exact assignment tuples only; learning may reorder those
  tuples within one episode.
- Never prune a subset, suppress an assignment permanently, or transfer state
  between episodes.
- Strict guards and `OnSegment` obligations are conflict atoms, never branch
  alternatives. Conflict provenance may overapproximate dependency but cannot
  authorize pruning.
- A continuous local-solver failure records no learned information.
- Runtime selector distinctness/tangency, guard, source branch, and untouched
  raw target must be replayed canonically before any authority.
- The baseline must retain at least 75% of callbacks and the side route at most
  25%, with exact callback accounting and failure identity.

No runtime selector forcing, CBJ reorder, connector, generated D0, or solver
execution was implemented in this source-only artifact. In particular, the
required wrong-first conflict, two-variable, periodic-sheet-plus-Intersect,
continuous-failure negative, ambiguous/tangent negative, open-bound negative,
and metamorphic panels remain future D0 obligations.

The development partition has 145 rows. All 102 non-development rows were
skipped by byte-level ID filtering before JSON deserialization. No individual
ID, formulation, target, truth, readiness result, or outcome was emitted. No
formal execute, scorer, full98, truth lookup, validation, or sealed source was
used. The census and deterministic replay were pinned to CPU14.
