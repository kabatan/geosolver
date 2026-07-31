# PARTIAL_RADICAL_BORDER_BASIS_HERMITE_V1 result

Disposition: `REJECT_SOURCE_GATE_REOPEN_OVER_TARGET_FIELD`.

The disposable generated D0 passed 4/4 positive families, 8/8 negative
families, 3/3 metamorphics, and 4/4 forged-certificate mutations, with zero
false authority and no global-completeness claim.  The truth-blind saved
proposal gate then produced 0 exact activations from 5 exact reconstruction
attempts (6 sources passed typed-cover/cap preflight).  Four attempts failed
rational moment reconstruction and one failed exact target-fibre vanishing.
The required gate was 4 sources and 2 structural signatures.

This falsifies the deployability assumption of this version, not the local
existence theorem: a cluster consisting only of configurations above one real
target embedding is generally not Galois closed over `QQ`, so its power sums
need not reconstruct as rational numbers.  Changing tolerances, radii, seeds,
or denominator caps is not a valid repair.

## Reopen gate

Reopen only when all of the following exist:

1. reconstruct moments exactly in the selected descriptor field
   `K = QQ(alpha)`, with `alpha` bound to the proposal's certified real-root
   isolator, rather than forcing moments into `QQ`;
2. refine proposal endpoints sufficiently to make bounded relative-field
   reconstruction auditable, without reading truth;
3. perform exact inertia/sign determination in the selected real embedding of
   `K` for every Hermite/Tarski query;
4. retain the complete equality/predicate ledger, exact matrix identities,
   proposal-box existence proof, raw-target descriptor check, and
   `completeness=false` boundary;
5. pass at least 4 saved sources and 2 structural signatures with zero false
   authority under caps frozen before observing that gate.

No formal scorer, validation/sealed data, case identity, or expected target
outcome was used.  Aggregate artifacts are `GENERATED_RESULT.json` and
`SAVED_ACTIVATION_RESULT.json`.

## Frozen hashes

- mechanism/entrypoint `candidate.py`:
  `6a262a73489d3ccf130be0d363b7c480e84b763885c9a1f6fe0d974a46f4ef31`
- saved-proposal runner `run_saved_activation.py`:
  `82cda9cc0de6be31366656411f72de7e1e7d68d25fb7bbff850184632fea2a8a`
- generated cases:
  `f711fc3a7be209eafb42bdb4b65c1392c1f31fa77cbb7cb87d1631a8cc2452a3`
- generated result:
  `1f67335bd7184d40d6e7f3b052e328cf87b249535011e47e1ebf1072f26c8b6c`
- saved activation result:
  `3a8bebf430ff0a1a79274e5331bc2bf321c403b9af3c977028a1503a97b65293`
