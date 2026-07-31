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
5. binds and exactly recompiles the existing cover reconstruction and replay
   ledgers, then embeds all algebraic model coordinates in one exact SymPy
   algebraic field;
6. reuses the existing `rur_semantic_replay` reconstruction rules for direct
   and bounded periodic source variables;
7. calls the existing full geometry `exact_replay/exact_runtime.py` on the
   untouched construction, constraints, bounds, guards and selectors, then
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

The first root census reached 33 primitive covers and four exact backend
witnesses, but the limited semantic runtime replayed none.  Repair A changes
only the representation/replay seam described above; backend caps, timeout,
and eligibility thresholds are unchanged.

The full candidate suite now passes 34/34.  Dedicated CPU14 reconstruction D0
passes algebraic auxiliary, periodic, and selector paths (3/3), rejects a
recompiled-ledger tamper, backend-target descriptor tamper, and wrong degree-
one proposal, emits no private witness/target/path, and has zero external
authority/release events.

No real panel, corpus source, truth, scorer, case ID, family, outcome,
validation, or sealed data was read while implementing or testing the
adapter.  The root benchmark owner exclusively runs the aggregate panel.

An independent review subsequently found that the first census runner did not
bound caller-supplied source paths.  This is now closed: only regular JSON
files directly under the frozen anonymous `degree1-inputs` root are admitted,
and source documents containing identity/family/truth/outcome fields are
rejected before compilation.  The complete ordinary-proposal connector is
described in `ORDINARY_BINDING_CARD.md`.
