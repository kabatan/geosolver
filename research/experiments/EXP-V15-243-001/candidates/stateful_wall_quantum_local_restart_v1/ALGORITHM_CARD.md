# STATEFUL_WALL_QUANTUM_LOCAL_RESTART_V1

## Hypothesis

Observed wall per callback could size a one-callback service quantum so that
every unserved start receives insurance work before one expensive local solve
occupies the search window.  This is distinct from fixed callback tranches only
if the live local kernel can suspend and resume its full numerical trajectory:
current/best point, partial Jacobian cursor, direct Broyden/raw-J model, trust
radius and LM damping, pending trial/acceptance window, callback ledger, and RNG
state.

## Source audit and decision

`HOLD_NO_CURRENT_FULL_STATE_SEAM`.  The current deep scheduler has an opaque
checkpoint-shaped policy API, but its live adapter explicitly rejects every
non-null checkpoint and returns `checkpoint=None,
checkpoint_resumable=False`.  Each rung launches the frozen local arm again
from the original start and charges the repeated prefix.

The frozen local kernel does retain the requested state internally during one
call, but `solve_local` returns only `CandidateOutcome(best.x, status,
counters)`.  Its caller returns only endpoints, statuses, counters, and lane
callback counts.  No trust/J/Broyden/pending-trial/RNG state crosses the call
boundary.  A best-x wrapper would therefore reset the model and is the already
tested progressive/deep restart mechanism, not a stateful quantum.

No prototype, connector, slow-evaluator D0, or wall threshold was created.
The predeclared gate requires a real current-kernel state seam, so changing
quantum size or forking the stopped kernel is not permitted.

## Required overlap audit

| Existing mechanism | Overlap | Why this does not reopen it |
|---|---|---|
| `progressive_local_budget_v1` | Bounded wall per fresh prefix and first-service breadth. | It declares checkpoint support false; a best-x restart is identical in state semantics. |
| `progressive_adaptive_hybrid_v1` | 64-callback probe, deep fresh handoff, wall cap, insurance. | Fixed callback progressive arms already had formal losses; this candidate may not repeat their schedule. |
| `deep_scheduler` | Opaque checkpoint API and charged rung reexecution. | The live adapter rejects resume tokens; the API shape is not numerical state. |
| `wave10_checkpoint_kernel` | Exact requested current/best, partial FD, Broyden/J, trust/LM, pending trial, ledger and RNG state. | It is a candidate-private replacement kernel, not the current local seam; prior parity and generated D0 already exist. |
| `wave10_callback_ledger_scheduler` / `stateful_halving_scheduler` | One-callback service, 25% insurance, resumed rungs. | Same-work generated benefit transferred negatively; the balanced aggregate stopped the lineage. |
| `wave10_wall_checkpoint_scheduler` | Wall-aware resumable checkpoint allocation. | It already overlaps the proposed observed-wall quantum and was not authorized for connection. |
| `wave11_callback_hazard_scheduler` | Dovetailing opaque resumable states under callback hazards. | Same stateful scheduling family; no new local transition or invariant is supplied. |
| `wave9_deep_scheduler` / `deep_scheduler_wave2` | Luby/geometric restart and wall dovetail. | Fresh restart schedules do not preserve the requested state and do not reopen the stopped lineage. |

## Reopen gate

Reopen only when the current promoted local kernel exports a source-bound,
serializable/resumable state containing every listed numerical field and
one-callback advancement has uninterrupted-trajectory parity.  It must also
provide a new runtime invariant explaining when retained model state is stale
or harmful; another timeout, tranche, Luby coefficient, geometric base,
insurance fraction, or best-x restart is insufficient.

No corpus, formal runner, scorer, truth, 98-case, validation, sealed input, or
individual case result was accessed.
