# Fixed-selection worker wrappers

## Preferred preload wrappers

`baseline_preloaded.py` and `champion_v1_preloaded.py` load the frozen
`PRECISION_RUNTIME` before search and intercept only the later request for
that exact path.  They preserve the original selection/finalization reserves:

- baseline: 1 / 2 seconds;
- champion v1: 3 / 3 seconds.

Separate cold processes replaying the saved 256 endpoints for `OMCB055(G)`
completed selection in 0.517 seconds for baseline (2 candidates) and 0.511
seconds for champion v1 (82 candidates).  Both are selectable as
`baseline_preloaded` and `champion_v1_preloaded` in `../run_arm.py`.

## Five-second fallback wrappers

These wrappers make one candidate-private reproduction change only:

- baseline v15 and champion v1 both use a source-independent five-second
  endpoint-selection reserve;
- total wall time remains 180 seconds and search remains 146 seconds;
- search, endpoint replay, HP, restoration, and finalization algorithms are
  unchanged.

`one_case_selection_probe.py` replays the saved 256 endpoints for
`OMCB055(G)` without reading truth.  On the current runtime it observed:

| arm/window | candidates | wall seconds |
|---|---:|---:|
| baseline / 1 s | 2 | 0.954 |
| baseline / 5 s | 2 | 0.501 |
| champion v1 / 3 s | 82 | 0.506 |
| champion v1 / 5 s | 82 | 0.499 |

The earlier zero-candidate cold-import failure did not reproduce after the
runtime caches had been populated, but the fixed window completed the whole
probe comfortably.  The wrappers' dry-run plans report the common 5-second
reserve and retain the 146/180-second search/total budgets.
