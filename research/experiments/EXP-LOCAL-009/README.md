# EXP-LOCAL-009 — feasibility-restoring line-search Gauss–Newton

Status: **rejected at T0; no T1, Core integration, or production promotion**

This experiment tested a truth-blind direct-box Gauss–Newton mechanism for the
guard/branch/domain failure class. It used declared residual scaling,
one-sided finite differences with sign/radius backoff, truncated CPQR,
effective clipped-step Armijo/model checks, and charged invalid-trial
restoration. It had no fixed damping, case routing, or solver fallback.

The outcome-independent six-case corpus and common Path A/B gate are preserved
in [`t0-preregistration.json`](t0-preregistration.json). Primary work was
common-assessor suffix-stable safe-full callbacks, right-censored at 4,800 per
case.

The candidate recovered eight qualified targets versus five for the control,
including three additional MultiRoot targets, at a work ratio of
`0.9901840491`. It nevertheless produced one unsafe NearRank endpoint and seven
strict-boundary ghost roots; StrictGuard was not safe-full. The zero-safety and
mechanism gates therefore rejected it despite the Path A recall signal.

[`t0-decision.json`](t0-decision.json) is authoritative. Candidate code,
runner, tests, and knobs were removed after rejection; the committed execution
revision named in the decision retains them for audit. The safe MultiRoot
signal is evidence for later discovery research, not permission for a
result-dependent solver portfolio.
