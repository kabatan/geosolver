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

The copied champion exposes the original single-core 180-second reference
window, but does not expose a resumable pending-work checkpoint or a stable
work-item sharding interface. GeoTarget therefore accepts longer requested
limits while reporting the actually used 180-second window, and rejects
`cores > 1` explicitly. It does not simulate continuation or parallelism in a
way that would change the selected algorithm. These two capabilities remain
blocked until they can be extracted byte-for-byte from frozen evidence.
