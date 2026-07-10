# EXP-SINGULAR-001 S3 claim boundary

This artifact is a bounded development negative result. It is not locked
validation, a product selection, or a general statement that good-Broyden
cannot converge at singular roots.

## Frozen result

- Input manifest SHA-256:
  `25b79616c5ea612232f80c6780de8a384e18e8fa50c906b1aae93a8918564012`
- Attempts SHA-256:
  `ae3cbc71d9185b913d259ac7b48e2df879e28b1191dd9bbe37c3ab3ae32c3189`
- Summary SHA-256:
  `e1ffa2c4db283fedfb031e40835cc7190b92199c99235cb229790d471de51b27`
- Independent analyzer SHA-256:
  `1f0fc066560d9674146ff615c36cd98f02f9b6234f6502d08e08ffccc5112e45`
- Harness source commit:
  `373f621d4da595af887cc3b03d9571284983025e`

The development split contains 30 cases in ten groups with three equivalent
signed transforms each. Twelve cases are the registered isolated/coalesced
singular stratum. S3 good-Broyden and its analytic inverse-secant control both
recovered 0/12 because each eligible trajectory set reached the globally shared
64-iteration limit. Every such outcome was `unknown`, had
`budget_exhausted=true`, contained no root evidence, and stayed within callback,
precision and wall limits. False, semantic-only and noneligible S3 promotion
counts were zero.

S1 promoted four noneligible regular cases. In the closest-root metamorphic
group it promoted one representation and returned unknown for two, so the
registered zero-disagreement gate also failed.

## What this supports

- The frozen S3 candidate does not justify product connection or locked
  validation under the registered budget.
- The endpoint-global work ledger correctly fails closed rather than silently
  granting each confirmation a separate 64-iteration allowance.
- The close-root transform group is a reproducible regression target for the
  existing S1 evidence gate.

## What this does not support

- It does not establish that good-Broyden is universally ineffective.
- It does not justify increasing the S3 iteration budget after observing the
  result.
- It does not establish isolated-root existence, uniqueness, or all-root
  completeness.
- It does not authorize S3 production code, locked-input inspection, or a
  stronger assurance label.

`product_connected=false` and `locked_validation=false` remain invariant. Any
S4 bordered-nullspace work needs a separate preregistration and frozen
development split.
