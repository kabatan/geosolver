# Numerical robustness and aggressive optimization audit (2026-07-29)

This directory freezes the decision evidence used to select the next product
optimization without copying per-case outputs or profiler binaries into Git.

## Decision

- The strict numerical-perturbation gate did **not** justify changing floating
  point semantics. Degenerate configurations can change local optimizer paths.
- A fused binary64 evaluation path was nevertheless bit-identical to the
  reference on 725 probes covering all 145 frozen cases.
- On six completed end-to-end cases, the fused path preserved every exact
  descriptor and produced a median 1.424694679x search speedup.
- On OMC024-F under the same fixed search budget, completed starts increased
  from 155 to 236 (1.522580645x), safe endpoints from 18 to 24, and the exact
  descriptor remained `([41, -841], real-root-index 0)`.
- A more aggressive native flat evaluator was substantially faster in a micro
  screen, but reached 4096 ULP difference. It is not qualified for production.

The product conclusion is therefore narrowly scoped: promote fused reference-
semantics evaluation to the full 145-case qualification gate; retain the
reference engine and do not promote the native-flat experiment.

## External archive

Raw profiles, per-case results and exploratory runners remain at:

`/home/kabatan/work/solver-artifacts/numerical-robustness-audit-20260729/`

At freeze time it contained 1,371 files and 69,916,724 bytes. The important
members and their SHA-256 values are recorded in `inventory.json`. This absolute
path is local provenance, not a product runtime dependency.

## Reproduction

`fused_evaluation_budget.py` is the exact audit prototype. It is retained here
as evidence only. Product code must implement the same general transformation
behind an attested product boundary and must pass differential, end-to-end and
145-case qualification gates.
