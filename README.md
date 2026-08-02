# GeoTarget

GeoTarget turns a V15 geometry problem into exact target descriptors with the
2026-07-22 champion algorithm. The product keeps a byte-identical frozen
reference engine and permits a separately qualified optimized engine. It
includes a Python API, CLI, loopback FastAPI service, and a React/SVG
construction workbench.

```bash
uv sync --frozen
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
uv run geotarget doctor
uv run geotarget validate examples/problem.json
uv run geotarget solve examples/problem.json --output result.json
uv run geotarget ui
```

For a local verification pass:

```bash
uv run ruff check .
PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
pnpm --dir frontend test
pnpm --dir frontend test:sites
pnpm --dir frontend build
```

The qualified default is the `optimized` engine in adaptive mode, with a
900-second safety cap and automatic physical-core selection. Its stable engine
hash is `224025b3113b59814bd354e8db2e4181cc64faf010f9de0eaf19d4cbe28f1868`.
The byte-identical `reference` engine remains available for the frozen
one-core, 180-second reproduction mode.
`no_answer_found` is not a proof that the source geometry has no solution. See
`CHARTER.md` and `docs/V15_GEOMETRY_DSL_AUTHORING_MANUAL_ja.md`.

Validation is non-coercing: the original JSON scalar types are preserved when
the document is materialized for the engine because the champion's exact
replay authority binds to those native source bytes.

The experiment evidence is preserved on branch `experiment` and tag
`champion-v2-poc-preloaded-20260722`. Raw artifacts are outside Git in the
checksummed freeze archive described on that branch. The research source
snapshots corresponding to the packaged frozen runtime are also kept on that
branch; `main` contains only the product runtime copies required for execution.

## Two-engine resource boundary

The frozen reference engine remains byte-identical, including its execution
order. A qualified optimized engine may change only an equivalent
implementation or scheduling. In both engines the champion thresholds,
optimizer, 600 callbacks per start, proposals, high-precision policy,
restoration, exact authority, and PointOnCircle semantics remain fixed.

The optimized engine has one search-budget exception: only when the first 256
starts produce zero accepted answers may it add deterministic batches of 64
starts, with `stability=2` and a `max_time_seconds` safety cap no greater than
900. Extension start ordinals have no numeric upper bound; only starts that fit
before the time cap may run. Finding an answer within the first 256 starts
disables this extension. No other proposal or seed lane may be introduced.

Resource coordination may shard only qualified equivalent work and must merge
attempts and exact descriptors deterministically. Requests that cannot reserve
the declared physical cores and memory fail instead of downgrading.
`no_answer_found`, including after the extension, means only that the bounded
run found no accepted answer. The existing `exact_complete` route remains
available only when the unchanged exact authority establishes completeness in
its supported scope; optimization and extension provide no new completeness
proof.

The optimized callback path compiles supported V15 DAGs as a whole problem.
For every other V15 program it still fuses the reference-semantics guard and
hard-feasibility snapshot, so unknown problems do not lose the general
speedup. The fusion is independent of problem identity and was bit-identical
on 725 differential probes over the frozen 145-case set.

The final qualification completed all 145 cases with zero lost reference
descriptors, zero truth-external exact descriptors and zero failures. Median
reported time was 55.66 seconds versus 136.28 seconds for the frozen reference;
p95 was 177.38 seconds versus 178.17 seconds. The full report remains outside
main and is checksum-bound by `src/geotarget/qualification.json`.
