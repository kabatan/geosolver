# Prior-overlap audit — checkpoint-genealogical AMS D0

## Audit gate

Before implementation, all Git refs and the extracted experiment runtime were
searched for `AMS`, `TAMS`, adaptive/multilevel splitting, first-passage,
genealogy/ancestry, and checkpoint-clone mechanisms.  The exact state tuple

`trajectory maximum score + first checkpoint crossing each attained level +
RNG ancestry + clone-from-crossing resampling`

was absent.  The candidate was therefore admitted as a new state, not as a
retry of stateful halving or Luby scheduling.

## Nearest prior states and the separating invariant

| Prior mechanism | Shared surface | Why it is not this mechanism |
|---|---|---|
| persistent SMC / replica exchange | population and source-only numeric evidence | frozen evidence explicitly had no first-passage trajectory genealogy or clone-from-crossing state |
| stateful halving | retains local checkpoints | ranks/prunes arms by best-half/Luby service; no ancestry, first-arrival level, or clone mutation |
| live checkpoint diversity | callback-level checkpoint service | allocates the next callback to an existing arm; it does not replace the minimum-score trajectory with a child of a survivor |
| static MLSL/APOSMM | multi-start global exploration | schedules starts and basins but has no trajectory-level first-passage path or RNG genealogy |
| Wave-10 checkpoint kernel | exact resumable local state | numerical transition substrate only; no population, level score, selection, ancestry, or cloning policy |

The stateful-halving best-half policy and Luby schedule are not imported or
reimplemented.  The copied Wave-10 kernel is used only for one-callback local
transitions and in-memory checkpoint state.

## Research reopen gate

The official [pyTAMS documentation](https://nlesc-etaoc.github.io/pyTAMS/)
describes trajectory adaptive multilevel splitting for rare transitions.  The
candidate applies that first-passage/clone principle to rare safe-root basin
discovery, while retaining a 75% independent numeric baseline.  This is a
mechanism hypothesis only; it is not evidence from real, formal, validation,
sealed, scorer, or truth-bearing cases.
