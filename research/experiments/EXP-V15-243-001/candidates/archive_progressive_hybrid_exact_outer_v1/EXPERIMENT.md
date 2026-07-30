# Progressive adaptive hybrid inside exact outer

## Composition finding

`progressive_adaptive_hybrid_v1/full_wrapper.py` already loads the same frozen
`champion_v2_poc_preloaded.py` stack used by the archive-reopen candidate. It
proves shared BASE identity and changes only these five search bindings:

- `SEARCH_WORKER`
- `SEARCH_ADAPTER`
- `SEARCH_CANDIDATE`
- `SEARCH_ARM`
- `EXPECTED_SEARCH_CANDIDATE_SHA256`

It does not install `exact_outer`. Therefore another historical/control wrapper
would be duplicate, but the exact-authority composition is not. This candidate
reuses `full_wrapper.configure()` on one historical object, then lets the
frozen `exact_outer_decorator` capture that object's unchanged PointOnCircle HP
callable exactly once.

## Mechanism and invariants

- Progressive `64 -> 600` search runs on the exact same BASE as historical
  champion-v2, the PointOnCircle repair, precision preload, HP, reservoir,
  restoration, descriptor authority, and zero-dimensional source authority.
- All positive-dimensional ordinary HP successes are proposals under global
  `CONFIRM_ALL_AUTHORITIES`. Publication requires matching exact source, guard,
  branch, primitive-minpoly, and root-ordinal replay.
- The zero-dimensional champion-v2 route bypasses search and numerical HP and
  retains its existing source-exact authority objects.
- The progressive scheduler retains a 25% original-order regular baseline
  handoff quota and a 25% counter-Cauchy insurance quota. No permanent pruning
  or case-dependent routing is introduced.
- The resource shim exposes only the reviewed per-core lease used by the exact
  child. It does not install a scheduler on ordinary historical HP.
- Hash or object-identity drift, a conflicting exact mode, authority mutation,
  missing baseline quota, or a second historical stack fails before execution.

No case ID, family, answer, expected target count, truth value, prior outcome,
validation, sealed data, or scorer input participates in the composition.

## Status

This is mechanism/source evidence only. The formal CPUs were occupied, so no
execute, scorer, real case, or recall/speed claim was produced. Promotion still
requires benchmark-owner evaluation under the common campaign gates.
