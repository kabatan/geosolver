# typed guard algebraic extension v2: independent re-audit

## Frozen disposition

- **PASS:** non-recursive source-root plus typed-guard certificate jobs emitted
  by `prepare_source_certificate_job`.
- **STOP (outside PASS scope):** recursive/disjunctive `Any` extension.
- **STOP:** standalone target authority and target-set completeness.

The PASS scope proves only one digest-bound local source root and its flat
typed guards.  A separate exact source-to-target link and final completeness
authority remain mandatory.

## Audited closure

- `typed_guard_adapter.py`: `1d93005c49cf4e3360b8b64449022be46e97ae59cc437ef889f5289e239709b4`
- `local_worker_adapter.py`: `711a14c9bcce7bd99c770768199f4b778b819434b1bcf0b9454024d0cea68150`
- base compiler: `f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318`
- prepare job: `0bf139408d81cf3c7d7cf938bf90acff519efa7e67caab093011e38ec18aee3e`
- Julia worker, inspected but not executed: `7086842164b868ff44ad3150a28b3836aae9898572e144e0cd3ad3953f553c14`

All executable Python hashes were unchanged after the CPU14 re-audit.

## Aggregate evidence

- unit tests: 21/21;
- generated primitive records: 60/60, false accept/reject 0/0;
- Angle canonical-range records: 120/120, false accept/reject 0/0;
- the old non-injective-cosine false-guard class: 12/12 fail closed,
  worker launches 0, false certificates 0;
- independent flat-guard records: 72/72;
- polygon oracle: 306 polygons, strict `AssumeConvex` equivalence 306/306,
  scale/translation/reflection invariance 36/36, false accepts 0;
- stored source-root binding replay: 4/4, stored negative controls 2/2 fail
  closed;
- source/system/job digest mutations: 6/6 rejected by consumer-side
  recomputation;
- an omitted `AssumeEq` consequence was accepted only with exact Groebner
  zero remainder; an inconsistent omitted equality failed closed.

Stored aggregate activation evidence is 208/243 interval-local-ready,
79/243 strict existing-worker shape and 20/243 exact-square verified.  No real
corpus or formal run was repeated in this audit.

## Findings

- The v1 P0 is fixed: Point Angle uses `[0, pi]`, Line Angle uses
  `[0, pi/2]`, and an Angle-to-scalar comparison without an exact constant
  range proof fails closed.  No new P0 was found in the PASS scope.
- One P1 remains in the standalone recursive helper: short-circuit `Any` can
  return true before visiting a later child with an unassigned symbol.  The
  admitted job adapter rejects every recursive guard before worker launch, so
  this helper is outside the PASS scope and the recursive route remains STOP.
- Digest verification binds immutable source bytes, canonical system and the
  unsigned job, but deployment must also pin this audited job-builder closure;
  digest equality is not a substitute for trusted compilation semantics.

No Julia, HP, global benchmark, real-corpus scoring or target authority was
executed or claimed.
