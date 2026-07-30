# Universal restart / current-champion checkpoint — STOP/HOLD

- `STOP_DUPLICATE`: fixed Luby original-start restarts already exist in
  `wave9_deep_scheduler`; its research prior also contains source-stratified
  Luby allocation.  The deep-scheduler lineage later stopped after two waves
  with `0/4` starvation recovery, three of four control regressions, and
  `-6.96%` source-solved/second.  A new cutoff, unit, schedule, or insurance
  share is not a reopen mechanism.
- `HOLD_PARITY`: the current scheduler API can carry checkpoints, but the
  frozen-v15 binding rejects non-null state and returns
  `checkpoint_resumable=False`.  The archived checkpoint kernel passed
  `440/440` callback-cut parity only against mature-kernel SHA
  `e9c9bd7f...`, before the current accepted-invalid retention and near-root
  strict-restart layers.
- Reopen only after the checkpoint state machine is ported to the exact current
  champion and passes every-callback trajectory/endpoint/counter parity.  No
  universal-restart or checkpoint code was retained in this worktree.

No formal truth, validation, or sealed input was accessed.
