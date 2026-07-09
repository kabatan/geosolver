# Cross-language protocol fixtures

The documents under `valid/` are shared Python/Julia codec fixtures. Consumers
must validate the parsed document and compare its RFC 8785 canonical bytes and
SHA-256 identity, not the pretty-printed source bytes.

`invalid/cases-v1.json` applies RFC 6902-style patches to named valid fixtures.
Each language must reject the patched document with the listed invariant code
or equivalent diagnostic. Plugin manifests are metadata projections; evaluator
callbacks are intentionally not serialized.
