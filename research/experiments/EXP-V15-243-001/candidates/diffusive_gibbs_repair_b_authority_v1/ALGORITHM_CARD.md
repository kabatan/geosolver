# Diffusive Gibbs Repair B — post-authority surplus service

## Hypothesis

Repair A preserved the search endpoint prefix but did not preserve the formal
exact-set service: a shared finite HP tranche could suppress a baseline
candidate and the shared deadline could shorten baseline exactification.
Moving DiGS across the final authority boundary removes both interactions.

## Mechanism

The frozen raw champion-v2 is connected to
`hp_scheduler_preserve_binding` with the process-global
`ADAPTIVE_NO_1280_POC` arm and then to `exact_outer_decorator` in
`CONFIRM_ALL_AUTHORITIES` mode.  The baseline executes with its unchanged CLI,
search, HP ordering/allocation, exact confirmation, descriptor construction,
and final atomic write.  Those result bytes are copied to
`FROZEN_BASELINE_RESULT.json` before any side action.

Only unused baseline search callbacks and at least 24 seconds of true outer
wall surplus admit the separate DiGS service.  Only the DiGS suffix is replayed.
Each side endpoint is passed back through the installed exact-outer HP callable;
release additionally requires `ordinary_and_exact_descriptor_identity_match`.
The nested exact fallback must itself carry passing authority. Accepted novel
descriptors and their proof-bearing HP attempts are appended after the
immutable baseline descriptor and attempt prefixes; counts are updated.
No side acceptance causes the baseline result object/file to remain unchanged.
The full baseline finalize reserve is never spent by the side lane. Every side
exception fails closed because the candidate RESULT write is the last action.

This is candidate-private one-file wiring.  It changes no public interface and
does not read case IDs, families, truth, expected target count, scorer output,
or previous outcomes.

## Reopen gate resolved

The old additive DiGS candidate can be reopened only after separating baseline
authority/finalization from the side service.  This candidate implements that
separation.  It does not reuse Repair A's claim of formal exact-set monotonicity.

## Evidence and limitations

- Source-only seam tests: 7 passed on core 15.
- Dry plan imports and verifies the frozen champion, resource scheduler, and
  exact-outer closure; the plan selects confirm-all exact authority.
- Baseline descriptor payload SHA/order, zero-surplus identity, side prefix
  union, real-worker list aliasing, and injected-exception byte fallback are
  directly tested.
- No scorer, truth, correctness outcome, development, validation, or sealed
  result was read or executed in this lane.
- This is a runnable D1 candidate, not a recall/speed claim.  The benchmark
  owner must perform the exclusive formal execution.  A side exact attempt may
  consume all remaining surplus; that can only forgo side gain, not baseline
  authority.

## Frozen hashes

- Worker: `1dd115da19b201a494b2fc2d20b51f6fbd66ef6008d959f09539cd06065840d6`
- Dry plan: `123218fb4613f7b7501b049b70473baa0e9d5db0b5475d7b38853a738af34831`
- Raw champion-v2: `241128047481cc8a428ff99dcb9d840cbc2ade3e87ddb564bb1a920fe10346ca`
- HP preserve-binding: `5453a30c46d3050c0520a6492f149595bf93d4f2794e3e1fa86d7d60c2365702`
- Exact outer: `05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7`
- DiGS full wrapper: `e2a64742bd2c10f3feb983ed2d7a3ca068d5505a738e3124ea6b56f2229c2135`
- DiGS search worker: `b5f7fb6c431346458a06a0893789e5f9012e3178b54ac57efeead423cea4de7d`
- DiGS search adapter: `856602efd5d1ac96464fa1a83dfad0f8f936b8dcd16ba5a95d0fad67371c22eb`
- Progressive candidate: `9a449d370a2a87dea50bf3aa9cd0a3cc3d1484491e48829fd89cbdd1c82b7972`
