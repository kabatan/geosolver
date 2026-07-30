# EXP-STRUCT-POLY-001 experiment card

Status: **generated S0 passed; static development applicability only**.

## Hypothesis

Whole-system polynomial recognition is too strict for mixed geometry systems,
but BTF decomposition can expose exact low-dimensional scalar polynomial blocks
without classifying the entire problem as polynomial. Solving only those blocks
may add basin/exactification proposals while the numerical baseline retains a
fixed quota and the canonical full-source verifier retains all authority.

## Combined mechanism

1. Extract residual-variable support using only source formulation structure.
2. Require a square, perfect-matchable, multi-SCC BTF plan.
3. Project each block's original constraints and required scalar aliases. No
   expression is algebraically rewritten or evaluated.
4. Reapply the unchanged `EXP-POLY-001` limits: at most three variables, degree
   four, 16 terms/equation, 32 total terms, 64 coefficient bits, 32 roots, and
   exact `QQ` syntax only.
5. Solve at most four qualifying blocks within a two-second combined wall
   envelope and a 32-element Cartesian cap. Replace only those coordinates in
   an existing numerical template.
6. Send every full proposal through the caller's canonical verifier. Guards,
   targets, source replay, and exact descriptor authority are not altered.

The portfolio keeps at least 50% numerical baseline and defaults to 75%.
Irreducible/non-square/parse-unsupported structure, zero strict blocks, invalid
templates, cap overflow, timeout, or worker failure returns 100% to baseline and
emits no proposal.

## Generated S0 ablation

A four-variable mixed chain contains one exact block (`x**2 = 1`), a dependent
scalar block, a transcendental block, and another dependent block. The direct
whole-system polynomial gate rejects it at the dimension cap. BTF alone exposes
four blocks but emits no symbolic proposal. The combination activates only the
first block, emits both exact roots, calls the full canonical verifier twice,
and accepts only the root consistent with the untouched template coordinates.

| Arm | Applicable | Proposals | Canonically accepted |
|---|---:|---:|---:|
| Whole-system polynomial | no | 0 | 0 |
| BTF structure only | yes | 0 | 0 |
| BTF then strict polynomial | yes, 1 block | 2 | 1 |

The active allocation was 12 baseline starts and four symbolic slots out of 16.
Generated irreducible and all-nonpolynomial controls each emitted zero proposals
and retained all 16 baseline starts. Degree, block-count, Cartesian, template,
and timeout caps also fail closed in unit tests.

## Truth-blind static development audit

The byte-level custody parser deserialized only the 145 `formulation` values;
row objects, sibling values, and problem IDs were not deserialized or retained.
No solver, scorer, answer, expected result, validation set, or sealed set was
used.

- Whole-system strict polynomial activation: 0/145.
- BTF decomposition: 27/145.
- BTF followed by strict block activation: 9/145 (6.21%), exactly one
  one-variable block in each activated formulation.
- Across 59 decomposed blocks: nine strict polynomial, 48 non-polynomial AST,
  and two dimension-cap rejections.
- Static combined detection: 127.556 ms total including lazy initialization,
  median 192.509 us, p95 475.119 us.
- Registered worst-case side-lane envelope: 18 aggregate seconds across the
  nine activated formulations; no symbolic solver was run for this audit.

This satisfies the applicability portion of the `EXP-POLY-001` reopen gate but
does not establish recall or speed. The next admissible step is a common-worker
development screen with an existing numerical template, full callback/source
replay accounting, and the same caps. Formal promotion remains unauthorized.

## Frozen full-v15 proposal-only arm

The common arm now loads the pinned champion worker only for combined-
applicable source formulations. Baseline search starts, callback limits, and
endpoint order are unchanged. A single generated side attempt uses the first
finite baseline endpoint as its anonymous template, runs for at most two
seconds, touches at most four strict blocks, and emits at most 32 Cartesian
proposals. Original endpoints precede every added proposal, so the side lane
cannot reorder or remove search discoveries.

The overlay is installed at the input of the champion's existing
`_fresh_replay_candidates`. The local symbolic route is explicitly given no
acceptance authority. The worker asserts that the original HP, restoration,
authority-descriptor, and descriptor-key function objects are unchanged after
installation. Source residual replay, guards, HP exactification, PSLQ/source
confirmation, and exact descriptor construction therefore remain the frozen
champion's responsibility.

An actual frozen-module generated smoke produced two symbolic proposals. Both
were presented to original source replay, which retained only the one
full-dimensional near root; local verified count remained zero. No baseline
endpoint was removed or reordered, and the side attempt remained under its
two-second cap.

A non-applicable generated dry run matched direct-frozen PLAN, stdout, and
stderr bytes. The formulation with source SHA prefix `63fb3e` is BTF-
irreducible and thus also follows exact frozen passthrough. Its 15-second safety
regression reproduced the missing search artifact (`TIMEOUT`) while completing
normally, preserving source bytes and total-wall compliance, with zero HP
attempts and no candidate telemetry. The common screen24 arm contract passed in
dry mode with no truth passed to the worker. No formal screen or scorer ran.

## Formal-owner aggregate and leftover-only v2

The benchmark owner disclosed only an aggregate S1 seed-0 result for v1:
safety clean, activation in 2/24 cases with two proposals each, score 15/24
versus control 16/24, wins/losses/ties 0/1/23, and wall time +0.39%. No case ID,
case-level result, expected value, scorer output, validation data, or sealed data
was disclosed to this lane. The v1 proposal arm therefore fails recall
promotion. Preserving endpoint order inside a shared capped replay/HP queue is
not sufficient: a later side candidate can still consume service that a
baseline wave would otherwise receive.

The reopen condition is implemented by `worker_v2.py` and
`leftover_overlay.py`. Before baseline service, the wrapper calls the original
fresh replay first and retains only source/endpoint object references; it does
not parse endpoints or generate proposals. It then calls the original service
with the exact original candidate object and deadline. Side work is eligible
only after the returned statistics assert all discovered primaries served,
primary/alternate/restoration waves complete, zero deferred primaries, and zero
unexamined backlog. It additionally reserves the champion's original finalize
budget and minimum HP attempt, then uses only the remaining wall time for a
bounded generator, a separate original source replay, and a second original HP
service.

If baseline waves are incomplete, no leftover slot exists, the proposal factory
fails, or later side replay/service fails, the wrapper returns the exact
original baseline result object. A generated trace records the strict order
`baseline_fresh`, `baseline_service_complete`, `side_proposal_generation`,
`side_fresh`, `side_service`; the original attempt trace is a prefix and the
original baseline statistics are preserved with side statistics nested under a
new key. Generated side proposals remain locally unauthorized. Non-applicable
dry PLAN/stdout/stderr remain byte-identical to direct frozen execution, and the
common screen24 dry contract passes. This lane ran no formal screen or scorer
and read no truth; the next gate is a benchmark-owner S1 rerun that first checks
baseline attempt/service-trace equality.

## Common-control binding audit

An integration audit confirms that both the formal-tested v1 entrypoint and v2
bind the registered common control directly at
`repro_20260722/workers/champion_v2_poc_preloaded.py`, SHA-256
`e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301`.
Neither entrypoint substitutes `finalist_numeric_worker_v15/worker.py` as its
top-level baseline. V2 now fails closed unless this exact path/hash and its
loaded layer graph match: precision preload, PointOnCircle champion-v2 wrapper,
PointOnCircle champion-v1 wrapper and periodic HP closure, then the original
champion-v2/v1 layers. This preserves champion-v2's zero-dimensional authority
route and the periodic repair applied to positive-dimensional HP work.

The truth-free source SHA `63fb3e...` remains BTF-irreducible and therefore
takes the exact `os.execv` no-op route. A fresh paired direct-control/v2 run at
15 seconds total, 5 seconds search, 16 starts, 32 callbacks/start, seed 0 and
CPU 0 produced byte-equal dry PLAN/stdout/stderr and byte-equal execution
stdout/stderr. RESULT semantics were equal after removing only the expected
nondeterministic `elapsed_wall_seconds`: both completed with
`SEARCH_DEADLINE_REACHED`, search classification `TIMEOUT`, zero HP attempts,
and zero descriptors. The v2 telemetry file was absent. Raw artifacts are kept
outside Git under `solver-artifacts/exp-struct-poly-001/common-control-binding-audit-v2`.

Therefore a candidate-side baseline-entrypoint mismatch does not explain the
v1 aggregate loss. The benchmark owner should still verify the independently
launched control arm's path/hash in its private run manifest before interpreting
the paired loss; this lane did not inspect that formal manifest. No scorer,
truth, formal benchmark, validation, or sealed data was used in this audit.
