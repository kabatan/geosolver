# LEDGER_DISCHARGED_LOCAL_VALIDATED_WITNESS — Repair A

## Hypothesis and mechanism

The frozen local Krawczyk lane rejects every nonempty replay ledger.  This
prototype accepts only digest-bound typed obligations and proves strict guards,
periodic sheet reconstruction, and intersection selection over the certified
box before calling the already-frozen localized target-factor link.  It does
not infer semantics from old free-form ledger strings.

The localized Gröbner/FGLM implementation is imported only after verifying its
frozen SHA-256.  This candidate adds no algebra backend and no compiler.

## Safety boundary

- Krawczyk certificate, source statement, job, and both ledgers are digest-bound.
- Typed coverage must be exactly the legacy-ledger set, with no missing or
  duplicate obligation.
- Strict relations must hold on the entire rational interval box.
- Periodic sheets are selected by exact rational turns and unique integer-sheet
  enumeration, never endpoint proximity.
- Coincident intersection alternatives fail closed.
- A verified result is still `authority=false`, `target_release=false`, and
  requires unchanged canonical source replay.

## D0 and disposition

Generated D0 passed **11/11** with zero false accepts.  It includes the old
global-membership failure/localized-factor success, strict boundary, periodic
sheet, selector, ledger omission, certificate mutation, and false-polynomial
near misses.

The truth-blind current-control-missing inventory has 13 square compiled
sources but **0** fit the frozen QQ/cost gate even after replay discharge.  Cap
expansion or backend tuning alone is not a valid reopen.  Therefore this lane
is **REAL STOP** without a heavy or formal run.

Reopen only when at least four sources across two obligation signatures fit a
theorem-backed exact-link gate without backend-only cap tuning.
