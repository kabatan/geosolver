# EXP-COEFFICIENT-MONODROMY-001

Candidate-private coefficient-parameter monodromy for small exact polynomial
blocks. See `ALGORITHM_CARD.md` and `results/generated-d0.json`. It is a
proposal route, not a completeness or output authority.

`thin_real_connection.py:connect` is the bounded real-source adapter. It reuses
the hash-pinned existing semantic compiler/reducer, accepts only a direct
one-variable square-free QQ block, preserves the baseline payload and
descriptor order byte-for-byte, reserves 75% of work for that baseline, and
returns only side descriptors accepted by a caller-supplied canonical replay.
The generated source-only result is in `results/thin-connection-smoke.json`.

`full_worker.py` is the runner-compatible Repair-A binding. It runs the
unchanged adaptive HP/canonical service first with its complete original hard
deadline, then uses only genuine leftover wall for the thin route. Every side
point returns through the captured fresh source replay and canonical service.
No remaining wall, no canonical addition, or any side exception returns the
exact baseline result object. See `results/full-worker-smoke.json`.
