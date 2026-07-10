# GeoTarget Python client

This package authors and validates canonical GeoTarget protocol JSON. It does
not implement numerical geometry semantics, run Python callbacks in the solver
hot path, or currently spawn the Julia application.

The public authoring API exposes a generic `ProblemBuilder` rather than
geometry-specific wrappers.
Every operation is a plugin-qualified open-world ID such as
`550e8400-e29b-41d4-a716-446655440000/example.geometry::intersect`. The
`validate` command checks both JSON Schema and graph-wide reference/plugin
invariants. Write `ProblemSpecV1.canonical_json()` to a file, then pass that
file to a Julia application with an explicitly allowlisted plugin registry.

Content identities are SHA-256 digests of RFC 8785 JCS bytes. This is a
cross-language wire contract, not an implementation-specific `json.dumps`
ordering convention.

## Minimal authoring pattern

```python
from pathlib import Path

from geotarget import PluginLock, ProblemBuilder

plugin = PluginLock(
    plugin_id="550e8400-e29b-41d4-a716-446655440000/example_geometry",
    version="0.1.0",
    core_abi="1.0.0",
    content_hash="sha256:" + "0" * 64,  # use the real Julia PluginSpec lock
)
builder = ProblemBuilder(plugins=(plugin,))
x = builder.variable("x", type_id=f"{plugin.plugin_id}::scalar")
relation = builder.call(f"{plugin.plugin_id}::constraint", x)
problem = builder.relation(relation).target(x).build()
Path("problem.json").write_text(problem.canonical_json(), encoding="utf-8")
```

The placeholder hash above is intentionally not executable; locks must match
the registered Julia `PluginSpec` exactly. For a complete runnable example,
including a real plugin, validation and solve handoff, see
[`docs/SDK_AND_PLUGIN_QUICKSTART.md`](../docs/SDK_AND_PLUGIN_QUICKSTART.md).

```powershell
uv run --project . geotarget validate ../examples/open_world_plugin/problem.json
uv run --project . geotarget build-info
```

`build-info` reports `julia_execution: "unsupported_not_wired"` until an
application transport is added; this is distinct from the implemented Julia
CLI in the repository.
