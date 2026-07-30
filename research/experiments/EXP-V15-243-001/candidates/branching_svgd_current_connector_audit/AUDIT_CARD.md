# Source-only seam audit card

- Base: `experiment@5f9dee88ad33422ae9a96fb5e3917b3ab53a2dfa`
- D0: `codex/exp-branching-svgd-d0@9cfdabc0`, mechanism SHA-256
  `7304dad59cad99b9d7cd29f839b14d5fd931eea2db1dd3accf037f18c9b1ad9a`
- Decision: `STOP_BEFORE_CONNECTOR`
- Audit kind: static source/hash inspection only
- Formal execute/scorer/truth/case inputs: none
- CPU execution: tests and audit on CPU 15 only

Audited layers were current progressive/adaptive adapters and workers, the
deep-scheduler boundary, the current near-root map adapter, exact-outer and its
authority boundary, champion-v2 zero authority, and the PointOnCircle wrapper.
All eleven source hashes matched the frozen expectations.

The audit distinguishes downstream authority availability from connector
availability.  Exact-outer and zero-dimensional authority both pass, while raw
numeric state, post-baseline tail lifecycle, two-stratum activation, same-ledger
replay, and exact side routing fail.  This is why no partial connector or
prototype wrapper was emitted.
