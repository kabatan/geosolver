# Checkpoint-genealogical adaptive multilevel splitting D0

## Hypothesis

A difficult safe-root basin is a rare first-passage event.  Independent local
starts discard the path information of trajectories that make unusual but
incomplete progress.  A small AMS side lane can retain that information and
branch from the first checkpoint that crossed a source-only residual/guard
level, without reducing the existing independent baseline below 75%.

## Frozen mechanism

- Score each trajectory by the lexicographic pair `semantic_valid`, then its
  maximum first-passage `-log10(||F||_2 + violation_inf + 1e-300)`.
- Record trajectory/root/parent ids, a SHA-256 RNG genealogy key, and the first
  in-memory checkpoint to attain each new maximum.  The initial first-arrival
  ordinal is preserved when its checkpoint is upgraded after the callback-free
  local-model construction at the identical accepted point.
- After mandatory breadth, select the lowest-score two trajectories (k=2 AMS),
  select a survivor that crossed their attained level, and clone its first
  crossing.  The pair receives equal-and-opposite weak-right-singular-vector
  perturbations.  This removes the arbitrary sign of an SVD tangent under
  coordinate reflection/permutation.
- Each mutation consumes one real source callback.  A semantic-valid mutation
  becomes the child trajectory's current point and requests a fresh local
  model; invalid or opaque mutations retain the kernel's fail-closed handling.
- The perturbation norm is a target-free function of trust radius, bounds, and
  genealogy RNG.  No case/family/id, answer, root count, target, scorer, or
  prior outcome enters the candidate.
- At least 75% of callbacks remain independent baseline work.  AMS receives at
  most 25%.  Neither arm uses dummy callbacks.
- Every reported point must pass a fresh replay through the original generated
  source.  Intermediate replay rejection is not treated as a root.

The local state machine is a direct copy of the existing Wave-10 checkpoint
kernel.  Upstream SHA-256 is
`da66047b399f01c5ee5ec6b042e4ae6ec279a5e43b982d82d103cf43daa210f4`.
The local file differs only in an environment-selectable experiment-root path
needed to bind the frozen extracted runtime; no common checkpoint framework or
serialization layer was introduced.

## D0 generated evidence

`GENERATED_RESULT.json` freezes eight seeds at 384 charged callbacks per arm:
288 independent baseline callbacks and 96 side callbacks.  The control spends
its side quota on independent trajectories; the candidate spends it on AMS.

- Positive families: narrow polynomial multi-root, banana-basin multi-root,
  and transcendental residual ridge.
- Negative/fail-closed families: guard-invalid low residual, flat no-root,
  score-misleading near-miss, and opaque evaluator.
- Safe-root gains occurred in 8/8, 8/8, and 7/8 seeds respectively: 46 unique
  replayed safe-root gains in total, with zero safe-root losses.
- There were zero false safe roots, zero branch fail-closed accounting events,
  and exact charged-callback equality in every arm pair.
- 270 ordinary-run genealogy branches activated, all using the weak
  right-singular direction.
- Nine signed-coordinate-permutation plus residual-swap/sign checks preserved
  the complete replayed root sets for both control and candidate.

This satisfies the requested D0 mechanism gate.  It does not establish real
recall, speed, or promotion safety, and no formal CPU (0–6), real case, scorer,
truth, validation, or sealed input was touched.

## Failure taxonomy and next gate

- If no valid first-passage hierarchy exists, the side lane spends real work
  on fresh independent starts.
- Equal/opaque score populations are not cloned.
- A missing resumable model, collapsed bounded perturbation, invalid mutation,
  or opaque source callback is fail-closed; it cannot create a reported root.
- The k=2 antipodal mutation spends two population slots and may be inefficient
  in a one-sided feasible chart.  Bounds clip both branches independently.
- The current scale cap is deliberately D0-quality and must not be tuned from
  individual benchmark cases.

Next gate: benchmark-owner review and a thin composition binding that preserves
the current exact/replay authority.  Formal measurement remains owner-only and
is not authorized by this card.
