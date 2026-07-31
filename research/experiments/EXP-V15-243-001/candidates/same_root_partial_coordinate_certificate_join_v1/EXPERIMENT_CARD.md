# SAME_ROOT_PARTIAL_COORDINATE_CERTIFICATE_JOIN_V1

- Status: `D0_PASS; ACTUAL_TRACE_GATE_NOT_RUN`.
- Hypothesis: exactification currently loses configurations when no one
  endpoint/rung recognizes every coordinate.  Coordinate-local minpoly,
  real-root ordinal and isolator facts can be unioned across finalized attempts
  without mixing roots if a fresh Krawczyk calculation on their hull proves one
  unique source root and its enclosure is contained in every contributing box
  and refinement.
- Mechanism: group only by exact source/guard/branch/raw-target binding; merge
  nonconflicting descriptor components per coordinate; require all components
  for all coordinates; recompute rational interval Krawczyk strict inclusion;
  then emit a proposal.  Hull uniqueness alone is insufficient.  Conflict,
  missing coordinate/component, disjoint box, unfinished artifact and binding
  mismatch all fail closed.  The unchanged QQBar source/guard/branch/raw-target
  replay remains the sole authority; this candidate never releases a result.
- D0: 9/9 passed.  The positive has x-minpoly, x-ordinal/isolator and complete y
  recognition at three different endpoint/rung records.  Endpoint/rung order is
  invariant.  Negatives cover two roots in the hull, disjoint boxes, descriptor
  conflict, missing coordinate, guard mismatch and an unfinalized partial
  artifact.  Candidate SHA-256 `480e56e9cd2746abc90295ac2edd966ff0f934194d6f3bc2496e862865d45f27`.
- Nearest evidence: `exact_coordinate_precision_continuation` recognizes
  coordinates independently but promotes complete configurations.  Its stored
  19-record successful panel contains only already-complete descriptors; failed
  real partial-coordinate facts and certified local boxes were not retained.
  Therefore it cannot establish incremental real activation for this mechanism.
- Next gate: under the existing HP lock, make one candidate-private run that
  retains finalized per-coordinate facts and local boxes only.  Continue only
  if at least two anonymous sources in two structural signatures become complete
  by a join while no constituent attempt is complete, all fresh Krawczyk gates
  pass, and unchanged exact replay has invalid/extra/authority failures zero.
  Do not build a trace platform or tune PSLQ degree/radius/precision to reopen.
- No truth, target value, outcome, case/family routing, formal benchmark, HP/CAS
  execution or shared infrastructure change occurred in this D0.
