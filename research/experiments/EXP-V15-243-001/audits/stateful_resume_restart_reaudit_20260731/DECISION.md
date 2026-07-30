# Stateful suspend/resume + universal-restart re-audit

## Verdict

`PRE_CODE_STOP_EXISTING_STATEFUL_KERNEL_AND_STOPPED_SCHEDULER_LINEAGE`

No candidate, connector, generated runner, or checkpoint framework was added.
No formal CPU, real case, scorer, truth, validation, sealed input, or
individual case result was read or executed.

The requested numerical state is already implemented.  The proposed Luby or
geometric freshening adds only a restart schedule to that existing stateful
solver and is therefore not a reopen mechanism.

## Direct existing implementation

`wave10_checkpoint_kernel` is a candidate-private callback-exact fork of the
mature local kernel.  Its `CheckpointState` already retains:

- current and best source-evaluated points and the complete callback ledger;
- a partial finite-difference Jacobian, column/retry cursor, and supported-row
  bookkeeping;
- direct Broyden and cached raw-J models;
- trust radius, LM damping, pending step/trial, acceptance windows, and model
  refresh state;
- generation/counter state and the PCG64 state.

`advance_one` charges at most one source callback.  The recorded parity result
reproduces the uninterrupted trajectory at all 440 callback cut points and
matches the frozen mature kernel on 8/8 applicable fixtures.  Cross-source
resume is rejected by an opaque source binding.  This is strictly stronger
than the requested same-process generator/coroutine state seam.

The matching scheduler lineages are also complete:

| Requested component | Existing lineage | Binding evidence |
|---|---|---|
| Resume one local start between callback tranches | `wave10_checkpoint_kernel` | 440/440 cut parity; current/best, partial FD, Broyden, trust/LM and RNG preserved. |
| Progress-aware one-callback service with 25% insurance | `wave10_callback_ledger_scheduler` | Equal-work generated D0: 159 gains, zero losses, zero false roots; thin checkpoint adapter already exists. |
| Stateful `32 -> 128 -> 512 -> 600` promotion | `stateful_halving_scheduler` | Full state survives rungs; generated restart ablation measured. |
| Cost-aware stateful scheduling | `wave10_stateful_scheduler`, `wave10_wall_checkpoint_scheduler` | Same-work/callback generated gains already demonstrated; the wall variant is held because the signal was unauthorized. |
| Callback hazard/dovetail retries | `wave11_callback_hazard_scheduler` | Allocation over opaque resumable checkpoints with mandatory breadth and 25% insurance already exists. |
| Luby restart | `wave9_deep_scheduler` | `original_start_luby_restart` and the one-indexed Luby sequence are implemented. |
| Geometric universal service prefix | `deep_scheduler_wave2` | Frozen `2 -> 4 -> 8 -> 16` wall dovetail; larger nonresumable rungs explicitly recharge original-start work. |

## Binding negative transfer evidence

`stateful_halving_scheduler` is the nearest causal experiment, not merely a
related checkpoint utility.  Its generated ablation preserved all positive
coverage while reducing callbacks from 45,200 for original-start restart to
40,480 for state preservation, a 10.44% reduction.  It covered slow curved,
narrow/guarded, anisotropic, singular, positive, negative, and near-miss
structures while preserving trust/damping across rungs.

The independently reviewed outcome-blind balanced-24 gate then regressed
source-valid coverage from 13/24 to 10/24 and exact-set success from 6/24 to
2/24, with no source-valid gain.  Its decision is `STOPPED / NOT ADOPTED` and
forbids case-specific remediation.  The toy same-work improvement requested
for a new D0 has therefore already been demonstrated and falsified at the
next transfer gate.

Repository-wide terminal audit further states that deep/stateful/successive
halving, wall-normalized multistart, and Luby-like variants are a stopped
scheduler-only lineage.  Combining the stopped stateful scheduler with the
already implemented Luby/geometric restart changes lane allocation and restart
times only.  It creates no new mathematical state or local transition.

## Current progressive/exact composition

The current `progressive_adaptive_hybrid_v1` policy has checkpoint-shaped API
fields, but its live adapter declares `current_checkpoint_support=false` and
uses charged original-start reexecution for the 600-callback handoff.  Its
all-start first service, 25% original-order baseline, 25% counter-Cauchy
insurance, deadline ownership, canonical replay, and exact outer are already
explicitly frozen.

Connecting the old stateful kernel would not be a thin activation of latent
state in the current local solver.  It would replace the positive-dimensional
local kernel/search adapter with the previously stopped candidate-private
fork.  Exact outer could remain downstream, but that does not repair the
negative search transfer and supplies no interaction theorem.  A Luby flag or
fresh-state counter would be only a schedule change, which the task explicitly
requires to stop before code.

## Reopen gate

Reopen only if a future local kernel exposes a materially new runtime
invariant that proves its retained model is stale or harmful and justifies a
specific state reset as part of the numerical transition.  The candidate must
then compare against the parity-passed stateful callback-dovetail control and
the stopped halving result under identical starts and work.

The following do not reopen this lineage:

- another callback tranche, timeout, Luby coefficient, geometric base, or
  insurance fraction;
- mixing some fresh lanes with some resumed lanes without a new state
  invariant;
- repeating slow-curved or narrow-basin generated fixtures;
- wrapping the stopped stateful fork in the current exact outer.
