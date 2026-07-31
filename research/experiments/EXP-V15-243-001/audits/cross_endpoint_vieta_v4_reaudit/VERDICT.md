# CROSS_ENDPOINT_VIETA_V1 v4 containment re-audit

Verdict: **STOP before root-custody dry/heavy execution.**

Frozen target: commit `366b568a830f24e549c50fddf279c5babac3633c`.
Inspected runner SHA-256:
`01873e2f97bec47cdf3f9d5d62309f496d9f4968187e2b0e7bab4a77ed356075`.
Inspected connector SHA-256:
`b6e9dd7bb5c62a657451fd18294cbceef032d6b764cace0628d878684faa2b41`.

The candidate owner's CPU14 suite reports 22/22 passing. This independent
audit additionally ran two CPU14, in-memory probes only. It did not read real
corpus artifacts, acquire the global lock, launch Julia, invoke a scorer, or
run a formal/heavy benchmark.

## What passed

- The former raw-source/projection contradiction is repaired. Original
  RESULT/PLAN/lane authority is bound to the id-bearing raw source digest,
  while candidate ranking and subset identity use the deterministic id-free
  projection. Crossed-id reuse and duplicate top-level JSON keys fail closed.
- RESULT, PLAN, and lane bytes are separately hashed. Their raw source digest,
  endpoint digest/bits, precision, numeric replay point/answer, guard,
  intrinsic-domain result, and canonical combined provenance are checked.
- Canonical replay constructs a square-free irreducible factor descriptor and
  initially requires raw-answer equality, target-link equality, a matching
  factor-local root ordinal, and multiplicity one.
- The worker passes the identical fallback object into a concrete union,
  retains independently accepted siblings, deduplicates descriptors, and
  derives emitted/dedup/unobserved counts from that union.
- Work and output paths are direct children of a mode-0700 temporary root, and
  the official lock path is checked on the inherited lock descriptor.
- The listed Python/source dependencies currently match their frozen hashes.

## Freeze blockers

1. **The materialized-union proof boundary does not bind ordinal or
   multiplicity semantics.** `union_observed_factor_records` verifies the
   proof digest and three boolean semantic flags, but does not require
   `factor_local_real_root_ordinal` or `attested_real_root_index` to equal the
   descriptor's `isolating_interval.real_root_index`, and does not require
   proof/descriptor multiplicity one. An in-memory mutation changed both
   ordinals to 7 and multiplicity to 9, recomputed the proof digest, and the
   union still emitted the record (`canonical_emitted_endpoint_count == 1`).
   This fails the requested attacker-recomputed-digest semantic check.

2. **The capability is self-issued, so a direct-child wrapper can impersonate
   the coordinator.** Authorization checks that a capability FD and official
   lock FD are inherited, but the capability has no coordinator-held secret,
   signature, preregistered nonce, or pinned parent executable. Any same-user
   wrapper can create a pipe, fill all public fields (including its own PID),
   open/lock the public lock path, and spawn `worker`. The code also does not
   require the authorization FD to be a pipe; a reusable regular file meets
   the read/EOF check. The only negative test supplies descriptors 0 and 1; it
   does not exercise a forged, structurally valid inherited capability. Thus
   arbitrary direct execution is made less convenient, not coordinator-only.

3. **The transitive exact runtime is not frozen.** The connector pins the
   Python executable, Python sources, DAG compiler, and base Julia worker, but
   the exact replay invokes bare `julia` from inherited `PATH` and a Julia
   project whose `Project.toml`, `Manifest.toml`, Julia executable, depot, and
   Nemo/FLINT artifacts are not in `FROZEN_DEPENDENCIES`. The observed project
   and manifest digests were
   `9f39a2eb827fcc842513037ed5d9debbe1e1cf15a24e29111645917e9acaa6c7`
   and
   `0b93cd67d522d4cce3bea7b3a754109a972e1eb2ef7fabe7eecb6c7a3cb19b42`,
   but the gate never checks them. Source-level closure hashes therefore pass
   while the proof-producing backend may drift.

## Minimal causal repair

- At union time, use an exact proof key set and require descriptor ordinal,
  proof factor-local ordinal, proof attested ordinal, and multiplicity to agree;
  add separate recomputed-digest mutations for each field.
- Replace self-describing capability authorization with a coordinator-created
  channel whose authenticity the worker can actually verify. At minimum pin
  the parent runner identity, require a FIFO/socket FD and consume a secret
  nonce that is not supplied by the work item/CLI; add a wrapper-forgery
  negative, not only a missing-FD negative. If same-UID hostile callers are in
  scope, an OS permission boundary or root-owned broker is required.
- Invoke Julia by an absolute hashed path and freeze/check Project.toml,
  Manifest.toml, depot/artifact closure, and relevant Python package closure
  before replay.

After those repairs, rerun only CPU14 unit/mutation tests, then return to the
benchmark owner for v4 custody-dry validation. No individual case, endpoint,
target, coefficient, or outcome was retained in this audit.
