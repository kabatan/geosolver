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

## P2 formal-execution-boundary repair (2026-07-31)

- Mathematical mechanism is unchanged (`candidate.py`
  `1f30a8e5c334d6e1d1c1583afe9b06d2d1d7a5c4c326209d93fafc7c775c5270`).
  The repair is candidate-private disposable code, not a common harness.
- The real runner now internally owns the shared `FormalRunLease`; every exact
  child needs the inherited lock FD plus a one-use parent-token HMAC. Direct
  guarded-worker invocation fails closed. Each attempt is a new session/process
  group with descendant termination and 10 GiB RSS, 12 GiB AS/data, 16 MiB
  file, and 2 MiB log caps.
- Python, Julia 1.12.6, the exact worker/candidate, numeric refiner, source
  runtimes, QQBar compiler/worker, Julia Project/Manifest, root-ordinal audit,
  and the complete 397-file legacy source tree are bound by runtime-closure
  SHA-256 `ec2d5c933d947549194e9226170702360a8e3d350d69b7c07267afe2624a55a9`.
- Every attempt copies and binds the untouched source bytes and canonical
  ordinary-proposal bytes separately. Terminal descriptors are accepted only
  after recomputing primitive irreducible square-free minimal polynomial,
  unique rational isolator, real-root count/ordinal, and exact replay parity.
  Aggregate and private sidecar publication is root-confined, atomic, and
  mode `0600`.
- Execution mutation D0: PASS 18/18, including 10 descriptor mutations,
  forged/missing lease proof, runtime/source/proposal byte drift, deadline,
  RSS/output caps, symlink and parent escape. No private/truth row and no
  global formal lock was used. Artifact
  `973ff03e7417e2e40e60dced2e4a79242967940b55dec673decdc118c5dc7bb5`.
- Mathematical generated D0 remains byte-identical PASS
  (`42057b0ef75da168e0da93241b1b20363e53e8f510b22dd5bca250e9b96c4285`);
  repaired anonymous static D0 remains 68 sources / 3 signatures PASS
  (`b843b60f0494bea0bf4fc8f01d0fb9e7b8f678eb03b79deeeb6ed0cf0758ab52`).
- Mechanism closure (seven code/test files) is
  `6723fc46a2212bc2fadfde8250ddcdc12eafad4a498c82fd72a06580c4bcc67a`.
  Pure-gain exact replay was deliberately not run in this repair lane. Freeze
  this closure and request independent adversarial re-audit before the owner
  schedules any global-lock exact gate.
