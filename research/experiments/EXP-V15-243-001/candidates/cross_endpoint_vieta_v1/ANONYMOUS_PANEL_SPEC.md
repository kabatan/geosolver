# Root-custody anonymous stored-endpoint panel

This panel is built and executed only by the benchmark owner. Candidate agents
receive aggregate counters, never request rows or individual outcomes.

## Private request schema

Each request contains:

- `schema_version = geotarget.cross-endpoint-vieta-panel/v1`;
- `source_projection`: the original solve JSON with only top-level `id`
  removed, serialized with sorted keys, two-space indentation, and one final
  newline;
- `source_sha256`: SHA-256 of those exact projection bytes;
- `subset_sha256`: custody digest of the frozen endpoint subset;
- `endpoints`: two through six observations.

Each observation contains `endpoint_float64_bits_hex`,
`endpoint_float64_sha256`, and independent `low` and `high` records.  A rung
record contains `precision_bits`, `provenance_sha256`, `raw_answer_decimal`,
and `full_tuple_decimal`.  The recommended frozen pair is 768/1024 bits.  The
provenance digest privately binds original RESULT, PLAN, lane bytes, source,
endpoint, and precision.  Both rungs must bind the same PLAN endpoint bits and
tuple dimension.

Original construction, constraints, bounds, guards, branch ledger, and raw
answer inputs remain in the root-owned replay closure.  They are not emitted
in the aggregate.

IDs, case/family names, paths, truth/Gold, target values or descriptors, known
target counts, control solve/miss, prior outcomes, scorer fields, and
historical labels are forbidden.

## Frozen selection

1. Authenticate source, RESULT, PLAN, and both HP lane artifacts under approved
   roots. Recompute id-stripped source bytes and source SHA.
2. Retain only endpoints for which the existing canonical source, guard,
   branch, and full-tuple replay passes independently at both rungs.
3. Group by source SHA. Deduplicate exact endpoint Float64 SHA values, reject a
   SHA collision with unequal bits, and require at least two unique endpoints.
4. Enumerate all combinations with degree 2 through `min(6,n)`. Rank them only
   by `sha256("vieta-subset-v1" || source_sha || sorted(endpoint_sha...))` and
   take the first 16 per source. Rank source groups only by
   `sha256("vieta-source-v1" || source_sha)` and cap at 32 groups and 256 total
   subsets. Freeze caps and order before execution.
5. Run the candidate, then replay every original full tuple with the proposal
   and that endpoint's root ordinal. One rejection rejects the whole subset.
   Completeness is always false.

No selection field depends on descriptor, proof progress, result, answer
magnitude, truth, or historical outcome.

## Aggregate-only output

Emit only total source groups/subsets, attempts by degree, bounded rational
reconstruction passes, independent-rung agreement passes, numeric-gate passes,
proposal count, full-tuple replay pass/reject/exception counts, activated source
group count, activated anonymous structural-signature count, and safety counts
for false/source-invalid/replay-bypass/fallback-mutation/completeness claims.
Also assert that identity, path, truth, and individual records were not emitted.

Do not emit polynomial coefficients, source/subset signatures, rows, targets,
or per-request reasons. The owner may privately join proposal passes against
the ordinary exactifier, but returns only aggregate gain and cluster counts.

## Frozen v3 authority correction

This section supersedes the earlier rung/replay details. The work-item schema
is `geotarget.cross-endpoint-vieta-private-subset/v3`; each rung additionally
binds the original RESULT, PLAN, and lane authority artifacts by path and SHA.
The connector recomputes those byte digests, PLAN endpoint bits, source and
endpoint bindings, 768/1024 tuple/raw-answer equality, and frozen numeric
hard/guard/intrinsic/original-DSL replay parity. Numeric parity and QQBar exact
replay are separate required conjuncts.

The root scout's 595 structural proposals are an upper bound. The whole Vieta
polynomial is structural only and is factored over `ZZ`. Each endpoint must
independently choose one square-free irreducible factor and factor-local root
ordinal at both rungs. Canonical replay receives only that factor descriptor.
Endpoint rejection is local; accepted siblings remain, descriptor identities
are deduplicated, unobserved roots are not emitted, the baseline union is
unchanged, and completeness is always false.

The root-only mode-0600 source-SHA sidecar contains only distinct structural
proposal source hashes. It contains no control or canonical outcomes and is
not part of the aggregate-only candidate result.
