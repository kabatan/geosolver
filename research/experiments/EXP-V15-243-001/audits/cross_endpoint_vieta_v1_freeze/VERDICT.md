# CROSS_ENDPOINT_VIETA_V1 freeze audit

Verdict: **STOP connector/gate; retain the mathematical prototype only.**

Frozen target: commit `876314ef03f6e60e00ab57928d2c23d8101f222f`.
The in-repository and external dependency hashes in `FROZEN_CLOSURE.json`
all match; the closure-file SHA-256 is
`7475e89abad287eb6b6ddfc028dc7d8c3ac16231b2cb67eebe73662ba1e489c4`.
CPU14 generated/unit validation passed 15/15 without Julia or corpus execution.

## What passed

- The whole reducible Vieta polynomial remains structural. Canonical replay is
  offered only a square-free irreducible factor and its factor-local ordinal.
- Low/high factor selection is independent, a rejected or exceptional endpoint
  does not discard accepted siblings, descriptor identities are deduplicated,
  and completeness remains false.
- Source-byte mutation, artifact-byte mutation, numeric guard/branch failure,
  and changed frozen dependencies fail closed in the inspected paths.
- The fallback object is carried through by identity, and numeric
  hard/guard/intrinsic parity is checked separately from QQBar replay.

## Freeze blockers

1. **Original-source versus semantic-projection SHA contradiction.** The stored
   HP authority binds the original source bytes, while the connector requires
   an `id`-free source and then requires RESULT, PLAN, and lane source SHA values
   to equal that projection SHA. Aggregate read-only inspection found top-level
   `id` in 145/145 formal-control inputs. In the inspected HP PLAN population,
   376/376 rows bound the original id-bearing bytes, 376/376 id-stripped
   projection hashes differed, and 0/376 projection hashes matched the PLAN
   source SHA. The frozen v3 connector therefore cannot activate on these
   stored artifacts. The unit fixture starts with an id-free source and does
   not cover this representation boundary.

2. **The aggregate-only process boundary is bypassable.** The public `worker`
   subcommand requires CPU14 and the runner hash, but not the official global
   lock, coordinator custody, or bounded-process parent. It accepts an
   independently supplied work item and output path and can write a private
   per-subset row. Thus the documented sole-entrypoint, global-lock,
   process-guard, and aggregate-only claims are not fail-closed.

3. **Emission accounting has no emitted descriptor.** Repair A retains only
   endpoint indices and descriptor-identity hashes; canonical replay returns a
   boolean and discards the accepted factor descriptor/proof payload. No
   baseline-plus-candidate result union is constructed. Nevertheless the gate
   labels the number of accepted identities as `canonical_emitted_endpoint_count`
   and hardcodes `unobserved_root_emit_count` to zero. Fallback identity is
   preserved, but observed-only emission and union behavior are not exercised.

## Reopen gate

- Introduce separate, explicit bindings for the original id-bearing source SHA
  and the deterministic id-stripped semantic-projection SHA. Reauthenticate
  original RESULT/PLAN/lane artifacts with the former and run exact replay on
  the latter. A root-custody dry validation must show nonzero aggregate
  activation before any expensive gate.
- Make worker entry possible only from the lock-holding coordinator (for
  example an inherited unforgeable descriptor/token), restrict private output
  to the coordinator-created temporary directory, and prove direct invocation
  fails closed.
- Return concrete accepted factor descriptors and proof records, union only
  those observed endpoints with the unchanged fallback result, and derive all
  emitted/unobserved/dedup counters from that concrete result.

No individual case, endpoint, target, coefficient, or outcome was retained in
this audit.
