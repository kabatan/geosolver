# Degree-one proposal adapter

## Scope

This is an aggregate-only adapter for the root-owned degree-one proposal
projection.  It adds no compiler, symbolic backend, source evaluator, or
authority route.

For each projection it:

1. validates a primitive, leading-positive degree-one polynomial;
2. derives its unique rational root and a fixed-width rational isolator;
3. calls the existing digest-pinned primitive cover and target-link adapter;
4. calls `candidate.prove` directly with the existing exact backend;
5. reconstructs raw coordinates from the existing model descriptors;
6. calls the existing frozen `ExactSourceRuntime` on the untouched source and
   exactly compares its raw target with the backend target.

Post-processing remains outside this raw-target theorem.  The endpoint is
validated as a finite ledger but is not passed to routing or the backend.

## Authority boundary

The root-owned input contains only coefficients, not the complete ordinary
proposal or its canonical hash.  Therefore an internal candidate witness is
counted only as thin-join viability.  The adapter never emits a witness,
coordinate, target, relation, source path, raw reason, or individual row.  Its
aggregate fixes `ordinary_full_proposal_binding=false`,
`degree_one_projection_only=true`, `authority_pass=false`,
`target_release=false`, and common integration HOLD.

The fixed output strata are the four categories already defined by
`applicability.py`; no dynamic structural signature or histogram key is
created.

## Generated evidence

The existing candidate and applicability suite plus four adapter tests pass
21/21.  The adapter positive reaches the existing backend, untouched source
replay, and exact target-link comparison.  Wrong proposal, post-processing,
and nonprimitive proposal negatives do not join.  The private per-request row
contains no witness, target, descriptor, or path.

No real panel, corpus source, truth, scorer, case ID, family, outcome,
validation, or sealed data was read while implementing or testing the
adapter.  The root benchmark owner exclusively runs the aggregate panel.
