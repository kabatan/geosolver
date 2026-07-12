# EXP-LOCAL-007 — SciPy/MINPACK Powell hybrid comparator

Status: **rejected at 48-case T2; no native port or production promotion**

This experiment tested SciPy 1.18.0 `root(method="hybr")` as a truth-blind
square-system local comparator after Trust Region, DFO-LS, and TRF candidates
failed earlier screens. It used declared residual scaling and a finite-box
`tanh` chart. Nonsquare systems returned typed zero-callback inapplicability.

T0 and representative-nine T1 produced a strong signal. T1 raised
family-equal safe-full from `0.571429` to `0.857143` and reduced
right-censored callback work to `0.499822` of the control, with support in six
families. Those outcomes authorized only the frozen T2 generalization study.

The 48-case T2 tied the control at family-equal safe-full `0.738095`, reduced
work by only 9.47%, regressed StrictGuard from `6/6` to `3/6`, regressed
MultiRoot from `2/6` to `1/6`, and produced five Gold-inconsistent close-root
endpoints. Both performance paths, the critical gate, generality, and safety
failed.

The prospective records and audited decisions are retained in:

- [`t0-decision.json`](t0-decision.json)
- [`t1-preregistration.json`](t1-preregistration.json)
- [`t1-decision.json`](t1-decision.json)
- [`t2-preregistration.json`](t2-preregistration.json)
- [`t2-decision.json`](t2-decision.json)

Candidate source, Python/SciPy dependency files, runners, tests, and knobs were
removed after rejection. The execution revisions named in the decisions
retain the exact implementation for audit.
