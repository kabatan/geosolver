# Checkpoint and resume

GeoTarget checkpoint v1 is the canonical, code-free snapshot used to pause and
resume deterministic solver execution. It is an explicit JSON protocol; Julia
`Serialization`, `eval`, dynamic module loading and embedded plugin code are
not part of the format.

## CLI

A normal source-tree solve uses the Julia application entry point:

```text
julia +1.12.6 --project=julia julia/app/geotarget.jl solve problem.json --options options.json --evidence evidence.json
```

To stop at a deterministic action boundary and write the resulting snapshot:

```text
julia +1.12.6 --project=julia julia/app/geotarget.jl solve problem.json --options options.json --evidence prefix-evidence.json \
  --max-actions 32 --checkpoint-out checkpoint.json
```

The Python command named `geotarget` does not currently transport solve
requests to Julia. A packaged application may expose the same arguments under
its own launcher.

To resume, set `checkpoint.path` and its exact `environment_lock` in the
`geotarget.solve-options/v1` document, then invoke the normal solve command.
`--checkpoint-out` may be used again to persist the new boundary. Evidence and
checkpoint output paths must differ.

The application reads plugins only from its explicitly injected registry. The
checkpoint's problem, plugin, policy and environment hashes must match both the
options reference and the newly compiled problem. Seed and policy version must
also match. Any mismatch fails closed before search continues.

The h/h2 endpoint-correction rollout uses solve API `1.4.0` and policy
`1.1.0`. Checkpoints created by the earlier measurement-only correction path
are intentionally not resume-compatible, although the checkpoint JSON schema
remains v1.

## Persistence and validation

The writer creates a temporary sibling and atomically replaces the destination.
The document is a closed `geotarget.checkpoint/v1` object with a SHA-256 hash of
the canonical `{target_image_status, state}` payload. Decode verifies the hash,
strict shape, typed numeric encodings and a canonical typed re-projection before
returning state.

The snapshot contains candidate history, pending proposals, refinement work,
scheduler counters, budget limits and charges, evidence events, the production
counter seed, precision, cancellation state and remaining wall time. Derived
candidate views and seen-task membership are reconstructed and checked from
history. Corrupt event sequences, impossible scheduler counters, inconsistent
budgets and unknown references are rejected.

Only built-in protocol payload types are accepted. Adding a custom plugin does
not extend the checkpoint decoder or install executable code; plugin execution
must continue to produce the existing typed proposal, observation and answer
state.

## Deterministic equivalence boundary

For the same problem, registry, options and total action prefix, resumed and
uninterrupted execution have the same typed result, budget, candidate state and
non-boundary evidence trace. A pause records an `EVENT_STATUS/paused` event, so
that explicit audit boundary (and evidence references whose digest includes it)
is intentionally present only in the paused/resumed trace. Remaining wall time
is reduced by compilation in every active solve invocation; time while the
solver process is stopped is not charged.

The schema is [`schemas/checkpoint-v1.schema.json`](../../schemas/checkpoint-v1.schema.json).
The cross-language fixture is
[`schemas/fixtures/valid/checkpoint-paused-v1.json`](../../schemas/fixtures/valid/checkpoint-paused-v1.json).
