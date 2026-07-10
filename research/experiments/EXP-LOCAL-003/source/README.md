# EXP-LOCAL-003 C0 generator boundary

This directory contains result-blind source only. It does not contain a
materialized development input, a solver outcome, or the C2 scaling mechanism.

Formal development generation is
`generator.py::build_development_documents(master_secret=...)`. The caller must
inject a fresh 32-byte C1 master secret; omission, zero entropy and every
checked-in deterministic test secret fail closed. Domain-separated HMAC-SHA-256
derives opaque case, latent-group, calibration, start, parameter,
representation and Gold identities. The parameter and representation keys
actually instantiate the problem/representation, so future locked values are
not predictable from this source.

The formal API builds three independent in-memory projections:

- `candidate`: 48 primary and 16 Safety cases containing only a full 64-hex
  `opaque_case_key`, Python-SDK `ProblemBuilder` document, 64 persisted
  calibration points, 32 starts, public numeric metadata and budgets;
- `assessor`: an unsealed generator-assessor projection (distinct from the
  formal closed assessor truth) with the matching key plus family/group/
  representation mapping, independent Gold configurations/targets and
  tolerances;
- `generator_private`: the replay vault. It alone contains the master secret,
  entropy/counter contracts, one normalized row per latent group, and case to
  group/representation joins. It must never be co-located with a candidate or
  formal assessor process.

`build_test_development_documents()` is a separate, explicitly test-only API.
Its two deterministic secrets are rejected by the formal APIs. CLI emitters use
only this test API.

`build_locked_documents(master_secret=..., locked_decision=...)` is frozen at
C0 but may be called only after a sealed, passing C3 authorization. It uses
fresh entropy domains and group indices 2 through 5, disjoint from development
groups 0 and 1, and creates four groups x eight families x three primary
representations = 96 cases. No CLI path emits a locked bundle. Static tests may
construct only explicitly test-secret, single-case locked descriptors.
The closed development decision record has exactly `schema_version`,
`experiment_id`, `card_sha256`, `development_gate_passed`, `selected_variant`,
`selected_path`, `safety16_disagreement_count`, `candidate_input_sha256`,
`development_assessment_sha256`, and `decision_commit`. It binds the card,
candidate input, sealed assessment,
champion/path, and authority Git commit. Its Safety16 disagreement count is recorded
but is deliberately not a locked-generation gate; it gates only later product
connection, as preregistered. The record contains no self-referential decision
hash.

Every problem travels through the public Python authoring model and canonical
encoder. The Julia `Local3FixturePlugin` is an allowlisted, otherwise unknown
plugin. Its codec-locked program literal and variadic scalar operations expose
only C0/Float64 value evaluation, including strict guard/domain roles. No
`DirectAnalyticProblem` enters this path.

`capture_calibration_truth.jl::capture_calibration_truth(candidate, assessor)`
independently decodes, freezes, compiles and evaluates all 4096 development
observations, or all 6144 observations in a future authorized locked stage. It
emits status/cost/z bits, `K`, nearest-rank `r`, clamped `a`, fallback/clamp/q
reasons and hashes. Before returning it rejects any primary semantic-z/scale-
permutation error or malformed development Safety `Q*z` construction; locked
capture accepts only the three primary representations.

The command-line emitters are explicitly test-only, ephemeral integration
helpers; none writes a research input tree:

```powershell
$env:PYTHONPATH = (Resolve-Path python/src).Path
uv run --project python --frozen pytest research/experiments/EXP-LOCAL-003/source/test_generator.py
julia +1.12.6 --startup-file=no --history-file=no --project=julia research/experiments/EXP-LOCAL-003/source/test_plugin.jl
```
