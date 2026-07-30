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

`full_worker.py` is the runner-compatible current-adaptive binding. It assigns
75% of the post-search service wall to the unchanged adaptive HP/canonical
service and uses only the remaining 25% for the thin route. Every side point
returns through the same fresh source replay and canonical service before its
descriptor is appended. See `results/full-worker-smoke.json`.
