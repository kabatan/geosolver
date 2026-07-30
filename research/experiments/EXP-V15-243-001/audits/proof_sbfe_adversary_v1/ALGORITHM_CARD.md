# proof-SBFE authority adversary v1

## Scope

This is a fixed synthetic trace corpus and an independent proof/budget oracle.
It is not a scheduler, a fuzzer, or a performance benchmark.  It reads no
formal/development/validation/sealed case, truth, scorer, result, or runtime
artifact.  Candidate execution is pinned to CPU15 and a caller-supplied SHA-256.

The frozen candidate snapshot is commit
`ee29f3e69835516e5c1271ba1627099d23840254`.  Its source is read only from the
candidate directory.  The adversary never changes candidate code.

## Fixed attacks

- two hidden tapes with the same revealed prefix but different future outcomes
  and costs;
- equivalent factored and expanded monotone DAGs;
- one shared leaf used by two descriptors, which must be evaluated and charged
  once;
- true and false terminal routes that must never be resurrected;
- the hard 75% baseline reservation and 25% graph cap;
- a late second leaf that must not complete a partial certificate;
- simultaneous leaf-ID, descriptor-ID, child-order, and insertion-order
  permutation.

## Authority boundary

A certificate is accepted by the oracle only if a complete canonical DNF route
is present in the revealed map and every leaf in that route is true.  A failed
descriptor requires a revealed false leaf in every route.  A late leaf is not a
reveal and cannot support either conclusion.  Every selected leaf must be a new
leaf on a still-viable route of an unresolved descriptor at that prefix.

The graph lane may account for at most 25% of total budget; baseline reservation
and spend must remain exactly 75%.  Equivalent graph representation and pure ID
permutation must not change normalized selections, terminal states, witnesses,
or budget accounting.
