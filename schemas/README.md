# Protocol schemas

These files are the canonical, versioned wire contracts for GeoTarget:

- `problem-spec-v1.schema.json`
- `plugin-manifest-v1.schema.json`
- `solve-options-v1.schema.json`
- `solve-result-v1.schema.json`
- `checkpoint-v1.schema.json`

JSON Schema validates the wire shape. The Python validator additionally checks
graph-wide invariants that JSON Schema cannot express, including unique node
IDs, valid references and locked plugin ownership of qualified operations.
Checkpoint validation additionally verifies the canonical content hash, resume
environment lock ordering, and every decimal-string UInt64 bound.

Checkpoint v1 is a closed, code-free state format. It stores typed values,
candidate history, pending work, the scheduler, budgets, evidence, RNG seed,
precision and remaining wall time. Derived candidate views and task membership
are rebuilt from history on restore. Plugin code is never serialized; callers
must inject an explicit registry whose locks match `resume_identity`.

Protocol identities use RFC 8785 JSON Canonicalization Scheme bytes followed by
SHA-256. JSON integers are restricted to the interoperable binary64 integer
domain; larger exact integers and UInt64 seeds use canonical decimal strings in
the fields that explicitly allow them. High-precision real strings use fixed
decimal notation without exponent, trailing fractional zeroes or negative zero.

Plugin relation manifests expose `truth_policy`. `required` is fail-closed;
`approximate_zero` is an explicit ABI promise that a false exact predicate may
be tolerated only at a nonzero residual that independently passes the numerical
residual bound.

The build carries byte-identical generated mirrors under
`python/src/geotarget/_schemas`. Edit this directory only through schema sync;
CI rejects drift from the canonical files here.
