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
