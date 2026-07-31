# EXACT_REPLAYED_GUARD_BILLIARD_PORTAL_V2

- Reopen gate: frozen wave20 G0 had `+95/-0` versus the one-reflection arm,
  342/720 activation, and exactly 7 false descriptors.  All 7 came from one
  causal defect: an approximate endpoint passed a strict guard and was then
  rounded to an exact descriptor on the excluded boundary without replaying
  that descriptor.
- Mechanism: direct reuse of the frozen multibounce billiard proposal.  The
  sole V2 change splits terminal admission into an approximate descriptor
  proposal and mandatory exact descriptor replay of source constraints,
  canonical strict guards, and raw target link.  Approximate endpoint guards
  are never authority.
- This is a safety reopen, not threshold/seed/path-length tuning.  Candidate
  SHA `a659ffc11505bc75b7df4a288a4d75e1277145d668d3ebf67d639215b9981a34`
  and runner SHA `9c165445990f87f67c2fdb7375b05e4761f5d586e2ef30797ca11d07eb38ca79`
  are pinned; billiard scheduling and work caps are unchanged.
- D0 is the direct frozen 720-case/120-metamorphic G0 corpus.  Required gate:
  false=0, gain/loss versus one-reflection `+95/-0`, activation=342,
  same-work true, metamorphic 120/120.
- No common framework, parser/compiler, scorer, solver API, or production
  integration is changed.  All terminals remain experiment-only.

## D0 result

- PASS: candidate 720/720, one-reflection and ordinary controls 625/720;
  `+95/-0`, false 0, activation 342/720, 584 reflections.
- Same charged work: 230400 in each arm.  Metamorphic 120/120.
- Aggregate artifact SHA-256
  `709192fe0c9834b8a1711a575d6921ef6a41b28ab9a7dcff0993a060c1a93d11`.
- V2 connector SHA-256 `candidate.py`
  `6bcbbceb511c2d8fcf4b9b217f56a43163da7e357bd9a483ea1393617386fc79`;
  direct G0 runner
  `7d22e3feb95e8876952b1e24aeccde405313d38948df12e890b1faf17e492e85`.
