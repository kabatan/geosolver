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

The exact-backend rollout uses solve API `1.6.0`, exact backend ABI `1.4.0` and
policy `1.1.0`. Checkpoints created by earlier solve-policy identities are
intentionally not resume-compatible, although the checkpoint JSON schema
remains v1. When exactification is enabled, the backend policy and environment
digests are part of `ResumeIdentity`; resuming without that backend, or with a
different build or recognition policy, fails closed.

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
history. Every proposed/observed event is also matched one-for-one to pending
work or candidate history, including its complete answer payload. Corrupt event
sequences, event/workspace disagreement, impossible scheduler counters,
inconsistent budgets and unknown references are rejected.

Before a restored `ExactAnswer` is returned, Core replays its built-in
certificate or dispatches to the bound optional backend. The C3A backend
reconstructs the algebraic coordinates and target, replays the original graph,
and checks the stored approximation, endpoint, branch, target identity and
target enclosure at 768 bits against the `1e-100` contract. A checkpoint hash
is an integrity checksum, not authority to skip this replay.

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
