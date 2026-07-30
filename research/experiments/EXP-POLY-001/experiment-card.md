# EXP-POLY-001 experiment card

Status: **generated S0 prototype; direct development route closed by static gate**.

## Hypothesis

For small source formulations that can be proved polynomial over `QQ`, an
exact Groebner/zero-dimensional solve can cheaply propose basins missed by
floating multistart without weakening source semantics. Applicability must be
strict: unknown operations or algebraic structure route to baseline.

## Research basis

- Faugère and Joux et al., [msolve: a library for solving polynomial systems](https://arxiv.org/abs/2104.03572), motivates specialized sparse polynomial-system machinery rather than a universal nonlinear replacement.
- [SymPy Groebner basis documentation](https://docs.sympy.org/latest/modules/polys/reference.html#groebner-bases) supplies the experiment runtime used here.
- Numerical/algebraic candidates remain subordinate to the repository charter's
  canonical source replay and exact descriptor authority.

## Frozen gate and controls

- Dimension `<=3`, square system, degree `<=4`, at most 16 terms per equation,
  32 total terms, 64 coefficient bits, 32 returned solutions, and two seconds
  absolute process cap; S0 uses one second.
- Only integer literals, exact integer division, variables, prior scalar aliases,
  `+ - * **` are accepted. Function calls, opaque constructions, branches,
  comparisons, floats, negative powers, symbolic denominators, and unknown
  names are baseline-only.
- Baseline quota is at least 50% and defaults to 75%. Timeout, positive-
  dimensional basis, solver error, or solution overflow emits no proposal.
- Every real finite exact root is replayed through the unchanged caller-supplied
  canonical verifier; guards and targets are never used for routing.

## Promotion boundary

Generated S0 may establish mechanism activation and safety only. Formal work
requires a frozen worker subprocess, source replay parity, aggregate callback
accounting, and a development-only common screen. No validation, sealed, scorer,
or known answer is used here.

## Truth-blind development applicability audit

The registered development145 container was scanned with a byte-level field
slicer. It deserialized only each top-level `formulation` value; complete rows,
sibling values, and problem IDs were neither deserialized nor retained. No
solver was run, and no scorer, expected result, gold value, validation set, or
sealed set was deserialized. The aggregate formulation-stream digest and
results are frozen in `development-static-audit.json`.

The unchanged strict whole-system gate activated on **0/145** formulations:
63 stopped at the three-variable dimension cap, 81 at the non-polynomial or
branch AST gate, and one at the variables schema gate. Degree, per-equation
term, total-term, and coefficient caps each rejected zero cases because no
remaining formulation reached them. The static detector cost 97.382364 ms in
aggregate including lazy SymPy initialization (median 6.810 us, p95 11.879 us).
With zero activations, the registered two-second symbolic process envelope adds
zero projected side-lane seconds and preserves the numerical baseline entirely.

This closes direct whole-system promotion. The reopen gate is either a strict
V15 source lowering that preserves exact semantics, or applying this unchanged
gate after a truth-free block decomposition exposes small polynomial blocks.
Either path must first show nonzero aggregate activation before a solver screen.
