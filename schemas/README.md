# Protocol schemas

These files are the canonical, versioned wire contracts for GeoTarget:

- `problem-spec-v1.schema.json`
- `plugin-manifest-v1.schema.json`
- `solve-options-v1.schema.json`
- `solve-result-v1.schema.json`

JSON Schema validates the wire shape. The Python validator additionally checks
graph-wide invariants that JSON Schema cannot express, including unique node
IDs, valid references and locked plugin ownership of qualified operations.

Protocol identities use RFC 8785 JSON Canonicalization Scheme bytes followed by
SHA-256. JSON integers are restricted to the interoperable binary64 integer
domain; larger exact integers and UInt64 seeds use canonical decimal strings in
the fields that explicitly allow them. High-precision real strings use fixed
decimal notation without exponent, trailing fractional zeroes or negative zero.

The build carries byte-identical generated mirrors under
`python/src/geotarget/_schemas`. Edit this directory only through schema sync;
CI rejects drift from the canonical files here.
