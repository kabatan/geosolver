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
champion/path, and assessment Git commit. Its Safety16 disagreement count is recorded
but is deliberately not a locked-generation gate; it gates only later product
connection, as preregistered. The record contains no self-referential decision
hash. `decision_commit` specifically names the already-sealed parent commit
containing the persisted development assessment in the external assessor-output
repository. It never names the separate candidate-evidence commit or the later
child commit that first adds the decision record.

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
uv run --project python --frozen python -B -m pytest research/experiments/EXP-LOCAL-003/source/test_generator.py
julia +1.12.6 --startup-file=no --history-file=no --project=julia research/experiments/EXP-LOCAL-003/source/test_plugin.jl
```

## Formal runbook

Every command below runs from the repository root on `main`. Stop on the first
error. A failed C1, C2, C3, C4, C5, or C6 transaction is terminal; there is no
force, resume, cleanup-and-retry, alternate output path, or replacement run.
The external repositories are fixed siblings of the main repository:

- `solver-vault/EXP-LOCAL-003/{development,locked}-assessor-vault`;
- `solver-private-audit/EXP-LOCAL-003/{development,locked}-generator-private-vault`;
- `solver-run-evidence/EXP-LOCAL-003/{development,locked}-candidate-run`;
- `solver-assessment-evidence/EXP-LOCAL-003/{development,locked}-assessor-output`;
- `solver-sandbox-scratch/EXP-LOCAL-003/` for pre-provisioned, per-run writable
  scratch directories that are physically disjoint from every evidence namespace.

Each leaf is an independent Git repository with its own object database. No
leaf may contain another repository or use Git alternates.

`seal_main_stage.py` is the only supported main-repository commit path for the
formal chain. It uses the environment-locked Git executable, disables external
configuration, hooks, attributes, replacement objects and signing, stages only
the exact additions for that stage without filters, verifies staged bytes and
the single-parent tree, and flushes committed objects and the `main` reference.

### C0 — environment and preimplementation freeze

The two commits are deliberately separate. The environment record joins the
complete C0 source tree; the preimplementation-lock commit must add only its
one lock file and must have that C0 commit as its parent.

```powershell
uv sync --project python --frozen
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/capture_environment_lock.py
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/seal_main_stage.py c0-environment
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/freeze_preimplementation.py
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/seal_main_stage.py c0-lock
```

### C1 — one-shot development input materialization

The preflight is read-only. `launch_c1.py` is the only supported mutating entry
point; its pure-stdlib launcher durably creates the attempt claim before it
imports project code. The three candidate/assessor/private projections are
created in staging directories, cross-checked, independently sealed, and only
then published with write-through directory renames.

```powershell
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/preflight_c1.py
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/launch_c1.py
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/seal_main_stage.py c1
```

The C1 main commit is the single child of the preimplementation-lock commit and
adds exactly the claim, two anchors, and four candidate-visible files. The
formal stage anchor never references the generator-private repository. The
separate audit-only private anchor binds it without making it assessor input.

### C2 — mechanism, tests, equivalence evidence, and execution lock

C2 is exactly five additions to the immutable C1 tree:

1. `julia/GeoTargetCore/src/local_model_transform.jl`;
2. `research/experiments/EXP-LOCAL-003/source/candidate_runner.jl`;
3. `julia/GeoTargetCore/test/test_local_model_transform.jl`;
4. `research/experiments/EXP-LOCAL-003/C2_L0_DEFAULT_EQUIVALENCE.json`;
5. `research/experiments/EXP-LOCAL-003/candidate-execution-lock.json`.

The evidence command may use only result-blind fixtures. It records exactly
`JULIA-CORE-DEFAULT` and `OPAQUE-PLUGIN-DEFAULT`, and requires byte-identical
L0 output from two fresh children per fixture: an immutable-C0 reference capsule and the
same capsule with the candidate mechanism explicitly disabled. C0 fixture and
golden bytes, the capsule manifest, read identities, and both no-capability
AppContainer attestations are bound in the evidence. Candidate input and both
C1 outcome trees remain inaccessible. Each suspended child-token probe denies
the main experiment root, the live C2 claim, and the fixed C1 candidate-output,
stage-anchor, and attempt-claim paths before resume. The exact ordered denial
set then covers the development assessor vault, generator-private vault,
run-evidence namespace, assessment-evidence namespace, sandbox-scratch
namespace, and main `.git` database. Thus neither C0 Gold/private truth nor a
prior/future outcome can be recovered from external storage or Git objects by
either untrusted child. Typed replay independently reconstructs each child’s
exact command, closed environment, runtime/depot/capsule read paths, and probe
order rather than trusting their persisted attestation.

The same evidence capture runs the future Julia test as a fifth, fresh,
no-capability AppContainer with a one-process job and the pinned Julia
executable directly as its root process. Its closed allowlist is limited to the
root Julia `Project.toml`/`Manifest.toml`, the `Project.toml` and `src` trees of
GeoTargetBase/Core/Geometry, the exact test source, the pinned runtime, and the
depot root plus only `packages`/`artifacts`. Nonrecursive grants on the
repository root and root `julia` directory permit Julia's project/workspace
discovery without granting any additional child content; `.git` remains
recursively denied. The mechanism is available only as
the bound file inside the GeoTargetCore source tree. The evidence binds the
exact command, environment, recursive flags of every read grant, stdout/stderr
hashes, exit/job accounting, read-identity commitment, ACL restoration, and
the recursively denied main experiment/C1 outcome/`.git`/five external
namespaces. A successful test is therefore part of addition 4; no post-C1 host
Julia test command is permitted. After the mechanism and its Julia test exist:

```powershell
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/launch_c2_equivalence.py
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/launch_execution_lock.py development
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/seal_main_stage.py c2
```

The execution lock allows only the two runtime sources. Tests and equivalence
evidence are immutable C2 authority but are never candidate-process sources.

### C3 — development candidate, assessor, and authorization

The candidate observer creates a fresh external repository with the append-only
chain `attempt -> raw -> pre-exit seal -> process exit -> manifest+authority`.
Only after the candidate process and its job tree have exited may the separate
assessor process open the assessor vault.
`launch_candidate.py` first creates a fixed durable, non-retryable external
attempt marker; the immutable candidate attempt record binds its exact bytes,
nonce and filesystem identity, the C0 launcher/observer/broker authorities,
the runtime-only execution lock, and the complete AppContainer request before
any candidate code or child process can run.
The runner uses the root `julia` project but receives only the root
`Project.toml`/`Manifest.toml`, the `Project.toml` and `src` trees for
GeoTargetBase/Core/Geometry, the exact candidate publication (including its
content-bound `plugin/Local3FixturePlugin.jl` and deterministic-gzip input),
the pinned runtime, and the depot’s `packages`/`artifacts` subtrees. The same
two nonrecursive repository/root-project discovery grants expose no additional
file content.
GeoTargetBenchmarks, C0 Gold/private files, and every unlisted path remain
outside the allowlist. The resolver independently rebuilds this ordered grant
list, including every recursive flag, plus the exact command and environment.

```powershell
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/launch_candidate.py development
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/assess_stage.py development
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/seal_main_stage.py c3
```

The persisted decision document's `decision_commit` is the external assessment
parent commit. The C3 anchor separately records the actual decision-child
commit. Locked materialization is allowed only if typed replay recomputes the
same passing assessment and decision.

#### Windows isolation threat boundary

The future C2 Julia runner and everything it can read are untrusted. The C0
launcher, observer, sandbox broker, and pre-exit sealing callback are trusted
protocol code whose immutable Git identities are recorded before launch. The
Windows kernel, administrators, the host account, and concurrent processes
with authority to modify observer memory are also inside this trusted-host
boundary; a formal run requires that host to be quiescent. The AppContainer
claim is containment of the candidate child, not containment of a compromised
host.

The callback is deliberately narrow and required to be operationally bounded:
it accepts one size-bounded frame only after the output pipe reaches EOF,
durably commits raw bytes plus the seal, returns one bounded ACK, and performs
no candidate evaluation. The callback itself runs in trusted observer space,
outside the child Job; the broker does not make an arbitrary callback safe.
Formal use therefore permits only the frozen C0 callback, and a stalled
callback makes the claimed attempt terminal rather than authorizing an
unisolated fallback or retry.

The observer propagates its remaining wall deadline to every Git subprocess
and checks it between trusted validation, compression, and durable-write
steps. Windows cannot safely cancel an arbitrary synchronous kernel I/O in the
same Python process; if such an operation itself never returns, external
termination is still required and the already claimed attempt remains
consumed. The Job likewise has no memory or disk quota beyond its one-process,
output-size, and wall-time bounds. These are explicit host-availability limits,
not alternative success paths or weakened evidence acceptance.

Each run uses a fresh no-capability classic AppContainer created with
[`CreateAppContainerProfile`](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile).
Its suspended root process receives security-capability, handle-list,
child-process-policy, and Job-list attributes through
[`UpdateProcThreadAttribute`](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
so Job membership exists at process creation rather than after an escape
window. The Job forbids breakaway, limits the run to one process, and uses
kill-on-close as described by Microsoft’s
[`Job Objects`](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
contract. Before resume, the broker verifies the exact AppContainer token,
Low integrity, zero capabilities, read identities, positive reads and denied
write/delete/ACL-owner access for every grant. Candidate children additionally
deny execute/traverse, read, every mutation right, DACL/owner changes, and
delete-child authority on the assessor/private vault roots, C0 source, run
evidence root, staging repository, durable marker, and future assessment root.
The main `.git` database is also an exact denied root for candidate and C2
children: repository history is never an input, and cannot be used to recover
otherwise hidden C0/C1 blobs by object ID.
The broker repeats namespace-mutation checks on every existing ancestor, so an
ambient `ALL APPLICATION PACKAGES` ACE cannot silently re-enable access. The
right-by-right denial manifest and entry count are persisted and independently
revalidated by the authority resolver. The broker holds input and scratch
identity handles through exit. Every held read entry must have no named data
stream and no extended attributes; named NTFS streams and nonempty EA blocks
fail closed, and their absence is committed in the read-identity manifest.
Closure additionally requires byte-exact ACL restoration, an empty Job,
deleted profile/storage, and empty scratch.

### C4–C6 — locked inputs, locked run, and terminal connection

C4 creates fresh generator-disjoint inputs from a valid C3 and commits exactly
the locked claim, two anchors, and five candidate-visible files. C5 then adds a
new locked execution lock without modifying the development lock or any prior
authority.

```powershell
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/launch_locked.py
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/seal_main_stage.py c4
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/launch_execution_lock.py locked
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/seal_main_stage.py c5
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/launch_candidate.py locked
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/assess_stage.py locked
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/seal_main_stage.py c6
uv run --project python --frozen python -I -B -S research/experiments/EXP-LOCAL-003/source/verify_final_authorization.py
```

The locked assessment has no decision and cannot reselect a variant. Its
external assessment commit has exactly two files; a single child adds only
`final-connection.json`. C6 is written and committed whether
`product_connection_allowed` is true or false, so a negative locked result is
an immutable terminal result rather than an invitation to retry.

The report-only `c1_materialization_times` boundary intentionally starts after
protocol, environment, and dependency validation. It includes input generation,
Julia compilation/calibration capture, and artifact projection, and excludes
Git sealing, anchor publication, gate verification, and primary oracle work.
The isolated/no-bytecode/no-site flags are part of every formal Python
invocation.  Each entry point rejects `site`, every pre-claim `site-packages`
path, coverage/profiler/telemetry injection variables, and any `__pycache__`,
`.pyc`, or `.pyo` below the protocol source or `python/src` before a project
module can be imported.  Python 3.12 resets `sys.prefix` under `-S`, so the
fixed `python/.venv/Lib/site-packages` directory is derived from the verified
`sys.executable` path and inserted directly only after the durable claim (or,
for read-only commands, after formal invocation validation).  The `site`
module is never imported, so executable `.pth` files are never processed.
Run all preparatory tests with `-B`, and confirm that both `source/` and
`python/src` contain no cache directory or bytecode before starting the formal
sequence.  These guards intentionally stay as small pure-stdlib copies in each
entry point: importing a shared project helper before validation would itself
reopen the boundary.  `test_formal_python_boundary.py` keeps those copies on
one tested contract.
