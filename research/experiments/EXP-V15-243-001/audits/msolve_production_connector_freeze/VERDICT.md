# msolve production connector freeze audit

Verdict: **STOP before selected-nine/heavy execution.**

Frozen target: commit `4a9150bfd8b03de6fd1f63a2fc2035661aec3a03`.
Freeze-file SHA-256:
`31d73964183b1bcc324e664ffa9e09efa1f82aa4171f1a820b585485e41506eb`.

This independent audit used source inspection and CPU14 generated probes only.
It did not execute msolve, Julia, a scorer, the global lock, or a formal run,
and it did not inspect or retain individual source/target/outcome records. The
candidate's saved/generated D0 records 12/12 passing; the independent generated
subset passed 5/5, and all *declared* dependency hashes currently match.

## What passed

- Full ordinary proposal bytes and SHA, id-free source bytes and SHA, exact
  Float64 endpoint bits and SHA, copied ordinary attempt, and original RESULT
  bytes are joined before admission. Source projection is checked against the
  original id-bearing source selected by the matching PLAN.
- Descriptor validation is case-independent and fail-closed: primitive,
  leading-positive, square-free, irreducible degree 1/2/4, coefficient cap,
  unique rational isolator, multiplicity one, and factor-local zero-based
  real-root ordinal. Generated degree 1/2/4 pass; degree 3, oversized BigInt,
  and wrong ordinal fail.
- The endpoint, not the ordinary target, selects the RUR box. The selected
  theta factor is exact, irreducible, square-free, multiplicity one, and has a
  unique isolator before QQBar source/guard/bound/raw-target replay.
- Compiler equations and predicates are added to the exact job. Replay counts,
  source raw-answer equality, target-link equality, truth false, and no
  completeness permission are checked.
- Child artifacts always state `authority_pass=false`, `target_release=false`,
  `PARENT_ACCEPTANCE_REQUIRED`; only the parent increments the public converted
  count in the cooperative process model.

## Freeze blockers

1. **Original PLAN provenance is neither exact nor byte-bound.**
   `_verify_original_plan_contract` accepts extra/missing semantic fields and
   requires only that `worker_sha256` look like any SHA and that execution and
   transitive manifests be arbitrary mappings. A generated PLAN with worker
   SHA `00...00` and `{"forged": true}` manifests was accepted. The matching
   PLAN bytes/path/SHA are not returned by `_verify_source_endpoint_origin`,
   are absent from `BoundOrdinaryProposal`, and are absent from the binding
   statement and conversion. Consequently the claimed full RESULT/PLAN
   provenance cannot be audited or cross-bound at acceptance. RESULT has an
   all-bytes digest but its own worker/transitive provenance is likewise only
   partially schema-checked.

2. **The compiler branch ledger is self-consistency, not replay evidence.**
   `_augment_job` compiles equations and predicates but never consumes
   `compiled["replay_obligations"]`. `exact_replay_ledger` checks allowed
   obligation shapes and a self-recomputed cover digest, then sets
   `canonical_branch_replay=True`; no exact-worker result field or job root is
   matched to the obligation ledger/hash/count. A generated branch obligation
   with attacker-replaced detail and a recomputed artifact digest was accepted
   as canonical branch replay. The existing negatives change the count or use
   an unknown kind, so they do not cover same-kind/same-count semantic mutation.

3. **The advertised transitive runtime closure is incomplete.** The direct
   scripts, msolve binary, Project.toml, and Manifest.toml are hashed, but the
   parent/child Python executable is checked only by reported version;
   `FACTOR_PYTHON` is checked only for existence; SymPy, mpmath, python-flint,
   and the geosolver runtime imported transitively are not hashed. Lossless
   transport invokes bare `julia` from inherited `PATH`; the Julia executable,
   depot, Nemo/FLINT package/artifact closure, and loaded shared libraries are
   not frozen. Thus `declared-closure-hashes-pass` does not establish a
   proof-producing transitive closure.

4. **Parent authorization is not an authenticity boundary in the shared-agent
   threat model.** The token is caller-supplied, its digest and every expected
   parent field are stored in readable JSON, and the child test itself builds a
   structurally valid authorization/token/run directory without a parent.
   Child output remains false-authority, which is good, but the parent accepts
   JSON from a same-UID writable raw directory using echoed public digests and
   booleans, without an exact output schema or an unforgeable parent-child
   channel. Another same-UID process can fabricate or race the conversion rows
   that the public aggregate counts. Mode 0700 does not isolate agents running
   under the same UID.

## Minimal causal repair

- Bind the unique PLAN's exact bytes/SHA into the ordinary binding statement
  and conversion. Validate an exact PLAN schema plus frozen worker,
  environment, and transitive-manifest hashes; apply the same exact provenance
  treatment to RESULT.
- Translate every compiler replay obligation into an exact job root/attestation
  (or return an exact executed-obligation ledger from the worker), and compare
  exact ordered ledger hash and count at acceptance. Add recomputed-digest
  same-kind/detail/source mutation negatives.
- Invoke hashed absolute Python/Julia executables and freeze the Python package,
  Julia depot/artifact, Nemo/FLINT, and shared-library closure actually loaded.
- If hostile same-UID candidate agents are in scope, move parent acceptance to
  a separately permissioned broker/UID or equivalent OS boundary. Otherwise
  explicitly downgrade the token to cooperative correlation, not containment,
  and never claim direct-child exclusion from it.
- Add crossed source/endpoint/RESULT/PLAN tests, forged-valid parent rows, PLAN
  manifest/worker mutations, exact child-output key sets, and executable/package
  drift negatives before any heavy pilot.

The degree 1/2/4 mathematics remains worth retaining. The STOP applies to the
production connector freeze and its authority/containment claims, not to the
BigInt transport or descriptor prototype.
