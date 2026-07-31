# REPLAY_GUIDED_RELATION_DOMAIN_CSP_V1

## Hypothesis

Some geometry sources contain a small exact finite coordinate domain even
when a monolithic numerical or symbolic solve is fragile.  Low-degree
univariate relations can seed every exact root; construction, constraints,
guards, and bounds can then propagate support by generalized arc consistency.
This may produce source-consistent full coordinate proposals for the existing
solver without using the raw target to select a branch.

## Static mechanism

The candidate projects only `variables`, `bounds`, `construction`,
`constraints`, and `guards`.  It replaces `answer` with the constant zero
before invoking the hash-pinned semantic algebraic lift.  Thus the original
raw target, `id`, family, truth, historical outcome, and expected target cannot
seed, prune, or order a domain.

Only `task=solve` with an empty or null `post_process` is admitted.  Source
bytes, total/per-expression characters, AST nodes/depth, integer bits, powers,
compiled expression size/operations, and coefficient bits are capped before
root enumeration.  Expected and unexpected symbolic failures normalize to a
non-applicable fallback.  Any anonymous census must additionally isolate every
row in a root-owned subprocess with a hard wall, RSS limit, and
repository-external output custody; the in-process algebraic caps are not a
substitute for that outer resource boundary.

Every low-degree univariate equality root is retained.  A relation is used to
seed a finite domain only when every already-bound support branch is itself a
complete finite univariate polynomial relation; an identically-zero branch
does not justify pruning.  Fixed caps bound variable count, relation count,
degree, domain size, support products, assignment products, and propagation
rounds.  Exceeding a cap or leaving any coordinate without a finite domain
fails closed to the byte-identical baseline path.

The candidate-only prejoin API stores the untouched baseline object and
returns that same object by identity on every non-applicable or exceptional
path.  This is only a seam test, not a solver integration; a future connector
must preserve the same identity invariant for timeouts, subprocess failures,
replay failures, and downstream authority rejection.

Generalized arc consistency removes a coordinate value only when an exact
relation has no supporting tuple.  Complete lifted assignments are then
compared with a fresh target-blind source replay, including canonical
construction selectors, constraints, guards, and bounds.  The emitted raw and
lifted coordinate assignments are proposals only.

An optional second audit replays the untouched source and raw target after the
proposal set is frozen.  It reports pass counts but never removes or reorders
proposals.  Both stages retain `authority_pass=false`,
`target_release=false`, and `target_set_completeness_claim=false`; any later
descriptor must still pass the existing canonical exact authority boundary.

## Current exclusions and reopen gates

- Periodic source coordinates are rejected because a unit-circle coordinate
  does not alone give a finite exact domain for the original phase sheet.
- Univariate polynomial degree is capped at four and root enumeration must be
  provably complete.
- Underconstrained positive-dimensional relations fall back rather than sample
  an incomplete coordinate set.
- A formal arm is not authorized by generated activation alone.  First run an
  anonymous, truth-blind static census.  Reopen formal integration only if at
  least three source signatures produce target-blind, full-replay-ready
  proposals and the root benchmark owner finds prospective control-missing or
  recurring-seed headroom.  Final release remains the current canonical
  source/raw-target authority.

## Generated S0 requirements

- unary roots are both present before an exact guard removes one;
- chained coordinate relations and Point construction propagate exactly;
- default intersection roots survive algebraically until canonical selector
  replay removes the non-source branch;
- changing the raw target or ignored ID cannot change proposal membership or
  order;
- constraint permutation preserves the exact assignment signature;
- underconstrained systems, truth-bearing inputs, and combinatorial overflow
  fall back;
- non-solve tasks and nonempty post-processing fall back without semantic
  rewriting, and fallback returns the untouched baseline object by identity;
- untouched full replay passes generated positives, while authority and target
  release remain zero.

## Frozen generated result

On exclusively assigned CPU14, the candidate-local suite passed `7/7` in
0.53 seconds.  Generated S0 reached `GO_STATIC_AUDIT`: all four positive
families produced proposal holds and every proposal passed the later untouched
full source/raw-target replay; target/ID changes and constraint permutation
preserved the assignment signature; root-before-guard pruning was observed;
and all underconstrained, cap, truth-input, non-solve, and post-process
negatives fell back.  Authority and target release remained zero.

Frozen SHA-256 values:

- candidate mechanism:
  `da92a984d6d3e4452649a87207835dca0bdbce28306108fd787aa6a35a60776e`;
- generated runner:
  `ed296d19080db4fe86e0cce365bf16c0adc482b6c894edaf0328104ae1a7004d`;
- generated result:
  `1bf6e273e4f148da3ad0a1e5ac7a57fdb2d4a2df09e91a493cf5e224689c1738`.

The root-owned anonymous degree-1 census subsequently stopped the lineage.
All 85 isolated row processes completed within their fixed caps, but the
candidate produced zero proposal-ready sources: 84 were rejected by the
target-blind semantic lift and one required unimplemented periodic source
reconstruction.  No proposal, replay authority, release, malformed/resource
row, or safety-boundary violation occurred.  No scorer, formal arm, HP
process, or canonical authority integration was run.

Decision: `STOP_ANONYMOUS_CENSUS`.  Reopen only with a new anonymous source
projection that passes the current target-blind semantic lift, or with a
separately generated and reviewed semantic-lift expansion that demonstrates
exact finite-domain replay before another census.  The same degree-1 panel
and current lift are not a reopen signal; periodic support additionally needs
a complete finite original-phase-sheet theorem.
