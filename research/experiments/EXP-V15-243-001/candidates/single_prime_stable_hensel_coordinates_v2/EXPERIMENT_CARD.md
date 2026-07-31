# SINGLE_PRIME_STABLE_HENSEL_COORDINATES_V2

- Status: `D0_PASS_REAL_GATE_PREPARED_NOT_EXECUTED`.
- Hypothesis: rational source-coordinate tuples can be recovered from one
  deterministic nonsingular p-adic branch without the old second-prime CRT
  Cartesian product.  Stability of the complete tuple at `p^5` and `p^6`
  rejects premature rational reconstruction.
- Mechanism: use the first degree-stable prime for which every observed
  modular root is nonsingular; lift each root once through `p^6`, capture the
  same branch at `p^5` and `p^6`, rationally reconstruct every coordinate at
  both moduli, require tuple equality, then substitute exactly into every
  compiled source polynomial.  No cross-prime product, CRT, Float64
  round-trip, target/truth/outcome input, or case routing.
- Terminal: the Hensel output is proposal-only.  Rational coordinates become
  linear QQBar descriptors `q*x-p` with point isolator/root ordinal 0.  Two HP
  lanes are used only for the target descriptor proposal.  The pinned
  `exact_coordinate_replay` document lowering, DAG compiler, guard lowering,
  QQBar worker and full replay-terminal validation are the sole source,
  guard, raw-target, descriptor and authority path.
- Nearest failures: frozen Wave-14 all-prime Hensel matched generated recall
  but cost `7.92x` direct and performed 328 cross-prime branch pairs; staged
  sibling added four-family conversions but cost `2.881x` its best control.
  Its reopen condition required source-native applicability and removal of
  exhaustive root/cartesian work.  This V2 removes the Cartesian limb and
  selects one prime; it does not reopen by tuning radii, prime order or target
  thresholds.
- D0 gate: rational positive systems, degree-drop recovery, multiple rational
  branches; singular, nonrational and `p^5/p^6` unstable negatives; variable
  and equation permutation.  Report CPU/work against the frozen old arm.
- D0 result: 7/7 generated cases and both permutation probes passed;
  proposal authority/release remained zero.  Exact substitution admitted five
  rational tuples and rejected the singular, nonrational and unstable cases.
  Against the frozen old arm on the same tiny panel, cross-prime pairs fell
  `12 -> 0`, lift steps fell 37.5%, and prime attempts fell 36.7%.  CPU was
  **not** faster: V2/old was `1.188x`; this is mechanism/work evidence, not a
  speed promotion. External result SHA-256
  `5fbb51a1cfc6f5e7401e5a8f394b95ada6532fd82a25add6f71dac2a1cdcded5`.
- The 108-source census is explicitly the frozen synthetic Wave-14 generated
  source-only panel (`generated_cases.py` SHA-256
  `41b5fab2f941e87119ca05beda535cdb4a6b3d4c7b283c0cffcc525bb373ef84`),
  not an actual development corpus: 96 found a deterministic good prime and
  51 produced stable exact-substituting tuples (107 proposals).  No case-level
  census output was emitted.  Prior actual static upper bound remains 9
  sources / 7 anonymous structural clusters.
- Prepared actual gate: fixed 85-row anonymous source projection panel,
  request SHA `ee424315...`, provenance SHA `c686498c...`, and bound aggregate
  of all 85 source bytes `c035f649...`.  Hensel receives no endpoint, HP
  relation, raw target, truth or outcome.  Only after a tuple proposal, the
  frozen ordinary-HP linear relation becomes an untrusted target descriptor
  at the QQBar boundary.  Promotion requires at least 2 replay-ready sources
  across 2 structural signatures and invalid authority 0.  Root may privately
  intersect accepted anonymous digests after freeze; no outcome-filtered panel
  is supplied here.  Julia/exact gate has not run.
- Frozen hashes: candidate
  `a5a113faf7bfa070e52edd21293ccf53bc05832a2c85cc74e787d60b109c5314`;
  exact connector
  `c56319e0830737f03e912eb371b0b6ca4c65917fc04e20c9252bd063b55ef30e`;
  prepared actual-gate runner
  `08b36f8ba980093b6d85e1f3f10e0c8b37913c6f00e509e93c037edea35901d0`.
