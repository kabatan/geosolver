# GeoTarget

GeoTarget turns a V15 geometry problem into exact target descriptors by running
the frozen 2026-07-22 champion in an isolated subprocess. It includes a Python
API, CLI, loopback FastAPI service, and a React/SVG construction workbench.

```bash
uv sync --frozen
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
uv run geotarget doctor
uv run geotarget validate examples/problem.json
uv run geotarget solve examples/problem.json --output result.json
uv run geotarget ui
```

The default and minimum time limit is 180 seconds. `no_answer_found` is not a
proof that the source geometry has no solution. See `CHARTER.md` and
`docs/V15_GEOMETRY_DSL_AUTHORING_MANUAL_ja.md`.

The experiment evidence is preserved on branch `experiment` and tag
`champion-v2-poc-preloaded-20260722`. Raw artifacts are outside Git in the
checksummed freeze archive described on that branch.

## Frozen-engine resource boundary

`cores=1,time_limit_seconds=180` invokes the frozen entrypoint byte-for-byte.
Longer limits first finish that reference window, then resume only record IDs
listed by the champion's own deferred-reservoir ledger; starts remain 0–255
and no seed lane is added. Multi-core mode keeps the frozen search on one core
and shards only the already-fixed HP/alternate/restoration wave ordinals,
merging attempts and exact descriptors in ordinal order. Requests that cannot
reserve the declared physical cores and memory fail instead of downgrading.
