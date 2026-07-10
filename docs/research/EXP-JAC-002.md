# EXP-JAC-002 — terminal protocol deviation

EXP-JAC-002 is terminal and nonpromotable. It produced no formal development
decision, no evidence-register entry, and no negative-result-ledger entry.
Locked inputs were never generated or opened, and production was never
connected.

## Violated invariant

The frozen card required:

> Product code, solve API and checkpoint identity remain unchanged until locked
> validation passes.

After preregistration, commits `efe5dea` and `4a179b8` added and validated a
`prepared_coloring` keyword on `GeoTargetCore.solve_local`. `solve_local` is
exported, and its `ProblemSpecV1` overload forwards arbitrary keyword arguments,
so this changed the product/public callable surface before locked validation.
The default compiled runner, `SOLVE_API_VERSION`, wire schemas and checkpoint
identity stayed unchanged, but those narrower facts do not satisfy the literal
card invariant. No preregistered amendment or ADR narrowed that invariant.

The earlier `jacobian_entries` seam from commit `d7ad9ba` is not contrary
evidence: it predates EXP-JAC-001, whose card did not contain the later JAC002
product-unchanged invariant.

## Run disposition

Two development executions were already ineligible before the protocol audit:

- `INFRA-JAC002-001` stopped before analysis when malformed prepared objects
  were found to be insufficiently validated.
- `INFRA-JAC002-002` completed under shared-host contention from EXP-COMP and
  main CI. Its summary was inspected, but all wall-time claims are contaminated.
  The clean integration omits its non-gating raw binaries and retains their
  summary and checksum digests in `infrastructure-invalidations.json`.

A host-exclusive rerun then started under the cross-worktree lease. Static
card-to-code audit found the protocol deviation after J0 had staged and J1 had
started. The run was aborted before staging verification, official publication
or outcome inspection. Its atomic audit is preserved as
`research/results/EXP-JAC-002/formal-run-audit.json`; the unopened, non-gating
partial J0 binary is not integrated and only its checksum is retained.

The canonical machine-readable record is
`research/experiments/EXP-JAC-002/protocol-deviations.json`. The official
governance summary is `research/results/EXP-JAC-002/summary.json`.

## Consequence

EXP-JAC-002 is neither an algorithm promotion nor a formal algorithm rejection.
Its development inputs and all observed or contaminated outcomes are pilot-only
and cannot be reused as untouched inputs. The prepared-coloring product commits
must not be merged. Any successor must remove the exported keyword, use an
explicitly authorized research-only seam, preregister a new generator and seed
namespace, and pass a new host-exclusive development and locked sequence before
any product connection.
