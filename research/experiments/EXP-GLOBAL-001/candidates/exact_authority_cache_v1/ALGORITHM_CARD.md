# Exact authority confirmed-identity cache v1

- Hypothesis: serial exact-coordinate confirmation wastes the fixed HP tail on
  repeated ordinary proposals for a target that already has proof-bearing
  source authority.
- Mechanism: cache only a successfully exact-replayed `(minimal polynomial,
  real-root ordinal)` and skip later ordinary proposals for that already
  emitted identity. Failed confirmations are never cached.
- Generality: no case/family/truth/known-count input. Descriptor use is limited
  to post-authority duplicate elimination already required by finalization.
- Safety: ordinary descriptors never become authority; the first accepted
  identity still comes only from the frozen exact-coordinate replay.
- Baseline/fallback: before the first exact success, behavior is the frozen
  `CONFIRM_ALL_AUTHORITIES` worker. Unique identities and failures retain the
  original path.
- Reopen gate: exact_outer fresh panel observed 19 ordinary-ready proposals,
  38.84 exact-child seconds, and a coverage loss caused by confirmation work.
- Reject: any exact-set loss in generated/metamorphic tests, any emitted
  duplicate/false identity, zero real activation, or no HP work reduction.

## Results

- Generated D0 preserved the exact set for duplicate-dense, unique,
  failed-first/alternate, multi-target, branch/raw-target, and ordinal-split
  fixtures. The independent adversarial suite passed 6/6.
- The 60/35 second screen24 diagnostic used the frozen exact-outer worker and
  fixed manifest. Paired seeds 0--2 tied exact recall at 14/24, 16/24, and
  16/24. Seeds 1 and 2 each had one timing-sensitive win and one loss; seed 0
  repeat had identical case statuses. No extra, invalid, or crash occurred.
- HP attempts increased 107->149, 114->175, and 109->172, with 47, 52, and 55
  confirmed-identity cache hits. This is real activation and a 39--58% HP-tail
  throughput signal, but not the campaign's completed-start speed metric.

Decision: `HOLD_PARETO_SPEED_SIGNAL`. Do not promote as a recall arm. Reopen
only when the saved exact-child work can be spent on an independent target
route or when completed starts can be measured under an exclusive formal run.
