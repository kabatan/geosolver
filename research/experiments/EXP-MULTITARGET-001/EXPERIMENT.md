# EXP-MULTITARGET-001 experiment card

## V2 reopen decision (current common arm)

The benchmark-owner-only S1 seed-0 aggregate for v1 was safety-clean but exact
14/24 versus control 16/24 (wins 0, losses 2). No case-level result or identity
was disclosed. This opens only the preregistered tail-sizing/replay-admission
gate: v1 reserved six HP seconds and changed reservoir replay from one to three
seconds before authority, reducing the control's first-answer budget.

V2 is a monotone post-authority extension of frozen v15. It changes no search,
replay, tranche, frozen candidate order, timeout, child runtime, source replay,
or authority behavior. Every frozen service event is retained as a prefix; only
after all frozen waves complete, and only if canonical authority already
passed, can truly unused wall slack admit a diverse deferred endpoint and its
failure-triggered frozen restoration. With no authority the complete trace is
control-identical. Full details and S0 evidence are in `POST_ANSWER_V2.md`.

V1 below is retained as negative-result evidence and is no longer the selected
common arm.

## Hypothesis

The frozen numerical-v15 tail can lose exact target recall when authority from
one endpoint suppresses a same-provisional-cluster alternate or leaves too
little explicit breadth for remaining target/configuration regions. Continuing
after the first exact descriptor and prioritizing anonymous diversity should
recover targets without changing canonical authority.

## Mechanism and applicability

- Require 28 seconds after discovery in formal 180/146 runs; common short
  30/20 runs automatically retain their full 10-second tail.
- Expand fresh source-replay reservoir selection from one to three seconds.
- Reserve six seconds outside primary tranche sizing for alternate/restoration
  work, with a three-second restoration sub-reserve after primary failure.
- Do not suppress an alternate because authority succeeded in its provisional
  cluster. Exact descriptor keys remain the only final deduplication authority.
- After authority, order pending work by 50% provisional-target novelty, 25%
  configuration novelty, and 25% residual quality.
- Apply to every numerical-v15 run. No case, family, source hash, truth, known
  target count, or prior benchmark outcome is used for routing.

## Frozen boundaries

- Parent numerical-v15 worker SHA-256:
  `330e52c75b98d3c58a1422cec415b5a53673ebafb7e90789a271df34a308309d`.
- Discovery worker, original-source replay, HP bridge, restoration worker,
  descriptor authority, and canonical source replay are unmodified.
- Final results retain schema `geotarget.exp008-finalist-numeric-worker-v15/v1`;
  overlay provenance remains in `PLAN.json` and `hp_schedule`.
- Deferred candidates remain unknown and no completeness claim is made.

## S0 evidence

- Unit/mechanism tests: 7 passed.
- Generated deterministic panel: 100 cases / 3 families; every panel serviced
  work after the first authority. The stop/suppress failure-model control kept
  100 distinct exact descriptors and the candidate kept 180 (+80), with zero
  descriptors beyond generated authority and exact duplicate dedup intact.
- Unscored 30/20-second development smoke: frozen search completed successfully,
  returned 9 endpoints and replay selected 3 candidates in 2 provisional
  clusters. The tail attempted one primary, one alternate, and one restoration;
  source bytes were unchanged and total elapsed time was 20.3814 seconds.
- The raw result records its executed scheduler digest explicitly. A later
  truth-free metamorphic counterexample changed only target-novelty ordering;
  see `METAMORPHIC_S0.md` and its separate mechanism digest.
- No truth, scorer, validation, sealed, screen24, or heavy formal run was used.
- Common frozen `run_dataset.py` two-phase acceptance smoke: 1/1 accepted,
  outer status `COMPLETE`, process `SUCCESS`, v15 result schema preserved,
  source bytes unchanged, and 20.5022 seconds within the 30-second budget.
  This acceptance artifact predates the target-affine ordering correction and
  records that transitive digest; the entrypoint CLI/result schema did not
  change. A formulation-only dry plan verifies the current transitive digest.

## Reopen/stop gate

Advance only through the benchmark owner. Stop if S1 shows an extra/invalid
descriptor, recurring exact-set loss, no post-answer activation, or work/time
regression beyond the preregistered gate. Reopen only with a causal failure in
tail tranche sizing, novelty ordering, or replay admission.
