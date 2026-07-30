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
