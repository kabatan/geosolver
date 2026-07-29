# GeoTarget Charter 2

GeoTarget is a Linux-local solver for finite-answer, value-seeking 2D geometry
problems expressed in the V15 JSON DSL.

## Product boundary

- The only numerical algorithm is the `champion_v2_poc_preloaded` algorithm
  selected on 2026-07-22. It has two permitted engine forms: a byte-identical
  frozen reference engine and an optimized engine. The optimized form is the
  product default only while its fail-closed qualification policy records both
  correctness and performance gates as passed. The reference form remains a
  permanent explicit option.
- The frozen reference engine and its execution order are immutable. A
  qualified optimized engine may change only an equivalent implementation or
  scheduling; it must not change champion decisions.
- Champion thresholds, optimizer, 600 callbacks per start, proposals,
  high-precision policy, restoration, exact authority, and PointOnCircle
  semantics are immutable in both engines.
- The only permitted search-budget extension is in the qualified optimized
  engine after the first 256 starts produce zero accepted answers. It may then
  add starts deterministically in batches of 64, with `stability=2` and a
  `max_time_seconds` safety cap no greater than 900. Extension start ordinals
  have no numeric upper bound; only starts that fit before the time cap may run.
  No extension is permitted after an answer is found in the first 256 starts.
- Product code may validate input, coordinate resources, isolate the engine,
  expose API/CLI/HTTP contracts, and present the construction UI. It must not
  change solver decisions.
- Numerical search never proves that no geometric solution exists. A result of
  `no_answer_found` means only that this bounded run found no accepted answer.
- The existing `exact_complete` route remains permitted only when the unchanged
  exact authority explicitly establishes completeness within its supported
  scope. Neither optimized scheduling nor the deterministic extension creates
  a new completeness or no-solution proof.

## Version-one scope

V15 JSON, Python API, CLI, loopback HTTP API, and the local Japanese-first
construction UI are product scope. Benchmarks, alternate algorithms, cloud
hosting, authentication, telemetry, collaboration, 3D, and legacy graph/plugin
compatibility are not.
