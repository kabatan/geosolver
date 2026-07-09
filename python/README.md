# GeoTarget Python client

This package authors canonical problem JSON and invokes the Julia solver. It
does not implement numerical geometry semantics or run Python callbacks in the
solver hot path.

M1 exposes a generic `ProblemBuilder` rather than geometry-specific wrappers.
Every operation is a plugin-qualified open-world ID such as
`550e8400-e29b-41d4-a716-446655440000/example.geometry::intersect`. The `validate` CLI checks both JSON Schema and
graph-wide reference/plugin invariants. Julia execution remains explicitly
unavailable until the application transport is implemented.
