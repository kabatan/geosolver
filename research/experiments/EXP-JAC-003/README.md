# EXP-JAC-003 preimplementation inputs

This directory implements only the frozen development-input and K0 public-control
capture stage.  It contains no cached Jacobian provider, no candidate routing
kernel and no product connection.

The governing order is:

1. `EXP-JAC-003.json` was committed on main.
2. `preimplementation-amendment.json` closed allocation and ABBA ambiguities in
   commit `6ac6572` before generator source existed.
3. The generator, independent assessor, public-baseline capture, K0 capture and
   one-shot materializer sources are committed with their resolved local-path
   Julia environment.
4. `public-baseline-snapshot.json` is captured twice, required to be
   byte-identical, and committed together with `baseline-capture-audit.json`.
   The audit retains the initial fail-closed attempt made before the new Julia
   environment was instantiated.
5. Those sources and the baseline snapshot are hashed by
   `preimplementation-lock.json`.
6. Only at the clean commit that introduces that lock may
   `source/materialize_development.py` be
   invoked once.  It refuses source drift, product drift, extra Julia/Python
   files, mechanism-like paths, prior output and a second invocation.
7. The materializer creates three separate immutable payloads: candidate-visible
   graph/starts, assessor-only Gold and analytic Jacobians, and pre-refactor K0
   public-control traces.  It copies and rechecks the already committed public
   API/checkpoint baseline; it cannot recapture or update the baseline.
8. Candidate/provider source may be authored only after those artifacts are
   committed and frozen.

The generator and control sources were first authored static-only while another
formal wall-clock study owned the host.  After that lease was released, the
in-memory separation tests and public-baseline capture were run; development
inputs remained unmaterialized.

The development partition has 16 cases in each of four new families and 32
saved starts per case.  Opaque IDs are the only join key in candidate-visible
data.  Family descriptors, numeric seeds, known roots, targets, branch truth and
analytic Jacobians exist only in the assessor payload.  The provider and route
must receive neither the opaque join key nor any oracle-program metadata: the
later runner may pass only compiler-derived dimensions/supports/color count to
the frozen route.

Locked inputs do not exist.  They may be specified by a result-blind author only
after a complete development pass under the rule in the amendment.

## Terminal formal-attempt appendix

The text above records the frozen preimplementation state.  Candidate and
formal-harness source were subsequently frozen and launched, but the development
attempt terminated in the frozen safety assessor on a JSON numeric-representation
contract mismatch before K0 preflight.  No K0 or K1 segment ran, the partial
archive contains zero segment traces and no terminal capture receipt, and the
independent host observation recorded contention and a monitor failure.

The post-outcome safety-only replay under
`research/results/EXP-JAC-003/development-failed-v0/` is forensic diagnosis only.
Its numerical aggregate is not part of the experiment evidence register or
negative-result claim.  It does not establish candidate correctness, formal
safety, efficacy, speed, or algorithmic failure.

`EXP-JAC-003` is terminal: no retry under this ID, no locked validation,
`locked=false`, and `product_connected=false`.  Reopening the research question
requires a new experiment ID with a preregistered serialization/assessor
contract, a clean host receipt, successful safety and exact-K0 preflights, and a
complete ABBA development run before any locked or product gate.
