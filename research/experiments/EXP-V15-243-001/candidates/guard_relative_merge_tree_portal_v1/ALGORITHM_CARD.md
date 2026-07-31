# GUARD_RELATIVE_MERGE_TREE_PORTAL_V1

## Hypothesis

Low-residual invalid endpoints can reveal a boundary-attracting basin without
making them answer candidates.  A residual lower-star merge tree on charged
finite observations can locate the first topological merge from such an
invalid component into a source-interior component.  Restarting from the
existing interior vertex at that merge may cross the attraction barrier while
retaining exact guard safety.

## Mechanism

- Use dimensionless source scales and the mutual-kNN graph with the fixed
  `k=min(2*n+1,N-1)`; duplicate vertices or a kNN cutoff tie fail closed.
- Define a low-residual invalid endpoint without a numeric threshold: it is a
  strict residual local minimum among its mutual-kNN neighbors.
- Insert vertices in strictly increasing residual lower-star order and use
  union-find to find the first merge of the invalid-minimum component with a
  component containing typed source-interior observations.
- Promote only the existing interior observation selected at that merge.  The
  midpoint from invalid minimum to portal is one charged side probe and is
  never itself an answer or authority candidate.
- No persistence cutoff, residual threshold, radius, or sweep exists.

## Dynamic gate and safety

Every pool must have complete typed guard coverage, only charged finite
observations, and at least eight source-interior observations.  Activation
requires at least three low-residual invalid endpoints across at least two
anonymous source hashes.  Unknown guards, uncharged/nonfinite data, topology
ties, or insufficient recurrence return the entire route to baseline.

Every fourth start is the maximum side allocation; all others remain baseline.
Midpoint evaluation is charged inside the same side budget, so baseline is at
least 75% and side is at most 25% for both starts and callbacks.  A portal is a
proposal only.  The unchanged local solver and canonical source/guard/branch/
raw-target replay remain mandatory.

No problem/family ID, target, answer, truth, or prior outcome is a routing
feature.  The anonymous gate emits aggregate counts only.

## Generated D0

Three generated dimensions/families supply three anonymous invalid minima and
eight interior observations per pool.  All 3/3 produce an existing interior
portal.  Eight focused tests cover guard/recurrence/interior gates, charged and
finite observations, kNN ambiguity, proposal authority, 75/25 accounting, and
observation-order/residual-scale/coordinate-scale invariance.  With 1,200
callbacks, the frozen accounting is baseline 900 and side 300, including three
midpoint probes.

This is generated mechanism evidence only.  The real dynamic gate is not run
in this lane; Root owns aggregate observation custody.  No corpus, formal
runner, scorer, truth, 98-case, validation, sealed input, or individual result
was accessed.

## Collect-only real gate connector

`collect_search_worker.py` loads the exact frozen champion-v0 search worker
(`ce2dd5...`) and replaces only the already charged `SourceOnlyCase.evaluate`
callable.  The original callback is called exactly once and its identical
return object is forwarded to the solver.  At most 1,200 unique finite typed
observations are retained in process.  Progressive residual calls are neither
replayed nor inspected, hard-feasibility-only failures are excluded, and no
individual observation is written to disk.

After the unchanged `search.json` exists, its existing endpoints are matched
against the in-memory pool.  Only aggregate `dynamic_gate` counts are written
to `search.json.guard-merge-gate.json`; the baseline result is SHA-bound and
left byte-for-byte unchanged.  The portal proposal and side quota are both
OFF.  The full wrapper rebinds only `BASE.SEARCH_WORKER`; search adapter,
candidate, arm, HP, reservoir, verifier, and canonical replay remain the exact
common-control objects.

Generated connector parity used the real frozen worker on a one-variable
strict-guard source.  With a completed fixed callback budget, collect and
baseline search results were equal after removing only elapsed wall time.
All 18 collect-focused tests passed on CPU14.  Root's collect-only screen24
seed 0 aggregate then supplied 11 complete typed pools with at least eight
interior observations, seven low-residual invalid endpoints across four
anonymous sources, 46,450 charged callbacks, 22,968 unique finite typed
observations, 399 endpoint observations, and zero accounting mismatches.  This
satisfies the frozen global dynamic gate.  No individual row or case outcome
was returned to this lane.

## Repair A: real-gate portal splice

`portal_search_worker.py` observes the same in-process pool and monkey-patches
only the frozen worker's `run_local_arm` binding.  The original three-start
splice produced zero activations in Root's frozen 72-pair screen24 run
(aggregate SHA `899671d...`; 60 UNKNOWN, 12 censored, 0 wins/losses).  Repair A
therefore executes immutable starts in complete four-start insurance blocks,
marks only endpoints already returned by those baseline lanes, and invokes the
unchanged structural selector after every completed block.  It stops at the
first existing source-INTERIOR portal, the fixed 75% baseline callback quota,
or deadline.  This changes evidence availability, not a numeric threshold.

One midpoint evaluation is charged inside the side quota, then that existing
interior vertex is passed as a start to the unchanged canonical local kernel.
The side callback cap is always at most exactly 25% of the original aggregate
cap, including the midpoint, even if baseline lanes finish early.  No original
start is replaced.  If time and the baseline allowance remain, every remaining
period-four product-Cauchy insurance start is scheduled before the other
remaining original starts.  HP, reservoir, verifier, canonical source replay,
candidate kernel, and search arm remain exact control.

Incomplete typing, missing endpoint minimum, kNN/residual ties, or no qualifying
component merge make the local gate UNKNOWN.  In that case the trailing
original prefix is run in order with the unchanged per-start kernel and full
original callback cap; no candidate counter is added.  Raw IEEE signed zero is
normalized only for endpoint membership after a generated +0/-0 metamorphic
failure; kNN and residual tie policy are unchanged.  The causal positive test
does not activate after block one, activates after new evidence in block two,
and retains all 16 generated original starts.  The frozen real-worker UNKNOWN
test remains byte-equivalent after removing elapsed time.  The assigned Repair
A D0 suite passed 11/11 on CPU14.  The fresh 72-pair screen24 rerun remained
safe (candidate/control invalid 0/0) but activated 0 times: all 72 candidate
runs were censored before a complete evidence block authorized the portal.
Wins/losses/ties were 0/0/72, while candidate work fell to 138,514 callbacks
and 1,989 lanes versus control 150,731 and 2,219; mean wall was 5.342 versus
5.290 seconds.  Repair A is therefore stopped.  Reopen only with prospective
evidence that a complete four-start block can finish within the same deadline
and expose enough typed endpoint structure; do not tune thresholds, k, radius,
or the deadline.

## Nearest mechanisms and reopen

Barrier/guard penalties are not reused: invalid endpoints never become
answers, and exact typed guard state is separate from residual.  This is also
not residual-only start ranking: the proposal requires a mutual-kNN component
merge into an already source-interior component and retains a 75% baseline.
If the real dynamic gate is zero, reopen only with recurrence satisfying the
same fixed gate; do not tune k, persistence, thresholds, or midpoint policy.
