# GeoTarget Charter 2

GeoTarget is a Linux-local solver for finite-answer, value-seeking 2D geometry
problems expressed in the V15 JSON DSL.

## Product boundary

- The only numerical algorithm is the frozen
  `champion_v2_poc_preloaded` implementation selected on 2026-07-22.
- Algorithm constants, work order, precision policy, restoration, exact
  authority, and PointOnCircle semantics are immutable.
- Product code may validate input, coordinate resources, isolate the engine,
  expose API/CLI/HTTP contracts, and present the construction UI. It must not
  change solver decisions.
- Numerical search never proves that no geometric solution exists. A result of
  `no_answer_found` means only that this bounded run found no accepted answer.
- Completeness is claimed only when the frozen exact authority explicitly
  establishes it within its supported scope.

## Version-one scope

V15 JSON, Python API, CLI, loopback HTTP API, and the local Japanese-first
construction UI are product scope. Benchmarks, alternate algorithms, cloud
hosting, authentication, telemetry, collaboration, 3D, and legacy graph/plugin
compatibility are not.

