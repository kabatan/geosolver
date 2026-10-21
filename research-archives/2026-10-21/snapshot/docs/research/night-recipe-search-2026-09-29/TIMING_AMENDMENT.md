# User-approved timing amendment — 2026-09-29 JST

**Superseded by [COMPLETION_AMENDMENT.md](COMPLETION_AMENDMENT.md).** The user
explicitly removed the time cutoff and requested completion of the original
plan. The text below documents the earlier bounded-wait policy; it is not the
current stopping rule. Run `timing.py` for the current policy (deadlines null).

The user explicitly prioritized ComfyUI: do not interrupt it; use the GPU when
available; the experiment may exceed thirteen hours somewhat. This supersedes
the original fixed wall-clock deadline and the pending ComfyUI-stop question.
There is no authorization to stop, unload models from, or otherwise control the
other project. Do not ask the same priority question again.

The experimental workload and all scientific comparison conditions stay fixed.
Credit actual GPU-contention waiting time, beginning with the guard refusal at
2026-09-28 18:14:32.631519 UTC, to both original cutoffs. Cap this credit at two
hours: the overall wall-clock upper bound is therefore fifteen hours, ending no
later than 2026-09-29 08:30:45 UTC (17:30:45 JST). The final 90-minute reserve
is preserved. Finish earlier if the planned work completes.

The original `clock.json`, protocol, configurations, and frozen manifest remain
unchanged as historical evidence. The authoritative current limits are calculated
by `timing.py` from `timing-policy.json` and `gpu-wait-ledger.json`; the current
snapshot is `effective-timing.json`. Do not use the original deadline in isolation.
The ledger records each wait interval once across process restarts. The launcher
closes an interval only when other compute processes have released the GPU.
Low GPU utilization alone is not sufficient while ComfyUI still holds memory.

`resume.py` overrides only the execution deadline with this calculation. The
temporary sleep inhibitor reads the same deadline dynamically and releases at
completion or the bounded deadline. Only the campaign's waiting launcher and
sleep-inhibitor processes are restarted to apply the change; ComfyUI is untouched.

This two-hour cap is a concrete operational interpretation of “somewhat beyond
thirteen hours,” not a new user-stated number. If GPU contention persists, report
incomplete evidence honestly rather than extending indefinitely or declaring the
learning hypothesis false.
