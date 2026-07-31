# POST_ENDPOINT_EDM_GRAM_EXACT_REOPEN_V1

- Hypothesis: a jointly rational squared-distance matrix can remain simple
  when independently exactifying every endpoint coordinate is difficult.
  Exact rank-2 Gram factorization plus two fixed source anchors reconstructs
  all selected points in one common quadratic field, with one global
  reflection bit rather than independent point signs.
- Mechanism: truth-blind source metric-structure gate; endpoint-only rational
  recognition of a complete squared-distance matrix; exact PSD/rank<=2 check;
  joint sign propagation; both fixed-anchor reflections; untouched replay.
- Scope: >=3 source point objects appearing in `Distance` structure and two
  exact fixed point anchors.  No target value, case/family identity, outcome,
  parser/compiler change, or inferred source mutation.
- Gates: static >=6 sources / >=3 point-count signatures; stored exact
  activation >=4 / >=2; baseline-failure-only exact replay gain >=2 / >=2.
  STOP at the first missed gate.
- Authority: proposal/prejoin only; `authority_pass=false`,
  `target_release=false`, no completeness claim.

## Results through stored activation

- Generated D0: PASS, 6 sources / 3 signatures, 76 exact pair checks,
  6 label-permutation checks, 3/3 invalid EDM rejections. Artifact SHA-256
  `42057b0ef75da168e0da93241b1b20363e53e8f510b22dd5bca250e9b96c4285`.
- Anonymous static gate: PASS, 68 sources / 3 signatures. Artifact SHA-256
  `5ff87fd6460cc6616f80073207ba4b86fab901071890605a533cf2cb266b79b2`.
- Anonymous stored gate: PASS, 26 sources / 3 signatures; 5 exact-EDM
  inapplicable, 37 failed the fixed-anchor/dynamic precondition, and no
  reconstructed branch failed float source replay. Artifact SHA-256
  `8d7b23370dea24fb5bb2041e0c07f69c1f270743c18b802096701d5ce6c103e2`.
- Pure-gain exact replay remains pending. Mechanism SHA-256 `candidate.py`
  `1f30a8e5c334d6e1d1c1583afe9b06d2d1d7a5c4c326209d93fafc7c775c5270`;
  real runner
  `2d46ac14710b934b6792ae2f4d2476b81def64e625602c9f0f55bf8963e1bf92`.
- Queue state: `REAL_GATE_BLOCKED_BY_GLOBAL_LOCK`, not a candidate failure.
  P1 audit repair pins the Python binary and outcome-blind panel provenance,
  rejects candidate endpoints whose Float64 digest equals the baseline,
  executes fixed ABBA with exactly two equal-timeout calls per route, and
  requires the full schema/source/parser/guard/raw-target terminal contract.
  The frozen pure-gain command uses the same anonymous panel SHA above,
  `--execute-stored --execute-exact --exact-timeout-seconds 20`, and the
  frozen exact-coordinate fallback worker
  `44d6fa802dc51e7f58e5a72e48b434a62be84275c328bd605f0e9e2f6eb11900`
  in fresh subprocesses. It has not been executed after the P1 repair.
