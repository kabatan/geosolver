# EXACT_TYPED_ANGLE_EQUALITY current-control connector audit

## Decision

`STOP_NO_EXACT_OPERAND_OBLIGATION_SEAM` for the fixed current formal-control
outer worker.  The source-only D0 mechanism at
`807be91de52e88b0587bc2ed30a8e6956baa12b1` remains valid, but it is not
connected to authority.

The only inspected runtime file was the root-authorized bind point:

- `/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/EXP-V15-243-001/candidates/exact_outer_decorator/worker.py`
- SHA-256 `05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7`

## Seam finding

The current outer worker sends source, source SHA, endpoint, endpoint SHA,
timeout, and output path to a frozen exact replay child.  It then accepts only
a fully verified final descriptor.  It does not export an exact typed-angle
operand pair, the D0 replay ledger, or a callback before the angle comparison.

A post-decorator could return the current result by identity on every side-lane
failure, but it could not add sound authority: reconstructing the missing exact
operands and every ledger precondition would duplicate the canonical replay and
would no longer be a thin source-only decorator.  Replacing or modifying the
frozen child would also violate this candidate's fixed bind/freeze constraint.

No timeout partition was installed, so current behavior, zero-dimensional
behavior, PGID, PDEATHSIG, and result bytes are unchanged.  The intended budget
contract remains baseline at least 75% and side authority at most 25% if the
reopen gate is later met.

## qreflect connector audit

The same fixed worker has no versioned qreflect/reflection obligation seam and
no reflected-source replay callback.  `qreflect` is therefore also
`STOP_NO_REFLECTION_OBLIGATION_SEAM`; it was not combined with the typed-angle
mechanism.

## Reopen gate

Reopen only when the frozen canonical replay exports a versioned, fail-closed
obligation containing both exact typed Angle operands and all D0 ledger facts,
or provides a pre-descriptor callback that it revalidates.  The outer boundary
must bind that obligation to source SHA, endpoint SHA, exact coordinate
attestations, target descriptor, root ordinal, and isolator.  qreflect requires
an analogous reflected-source obligation.  Only then may root allocate at most
25% authority budget and run formal measurement.

## Evidence scope

- Generated D0 only, pinned to CPU15.
- Source activation utility emits aggregate counts only; root owns screen24
  invocation and activation decision.
- No formal benchmark was run.
- No scorer, truth, result, corpus manifest, or individual correctness was used.
- The isolation incident is recorded minimally in `INCIDENT.json`; work after
  it was source-only.
