# EXP-SEMISMOOTH-001: typed active-stratum semismooth proposals

Status: **D0_PASS / HOLD_COMPILER_CONNECTION**

## Hypothesis and reopen gate

The audit premise is that `127/133` sources receive a conservative nonsmooth
flag.  The candidate therefore does not route on that coarse flag.  It admits
only a small typed scalar DAG (`abs`, `min`, `max`, `piecewise` plus smooth
arithmetic), and activates only when the numerical point is on a mechanically
identified branch seam.

The closest prior candidate, `epoch_a_semismooth_generalized_jacobian_g0`,
gained `+300/-0` under equal work but stopped after 6/630 metamorphic failures:
a duplicated nonsmooth row multiplied its row-wise Cartesian bundle and
changed the selected four proposals.  This experiment is the permitted causal
repair: choices are keyed by structural branch site and form complete
whole-matrix strata.  CSE and duplicate residual rows cannot create new branch
sites or an order-selected subset.

## Mechanism

- Enumerate the currently selected stratum and all adjacent ambiguous strata,
  capped at eight.  Unsupported/opaque DAGs and larger products fall back.
- Form one row-normalized semismooth Newton proposal per distinct regular
  whole-matrix model.
- Re-evaluate the proposal with normal typed-DAG branch selection and keep it
  only when every active branch identity matches the model that produced it.
- Keep nine of ten scheduling units as literal ordinary baseline work.  The
  side lane is fixed at 10% and never emits an answer directly.
- Guard/semantic checks and eventual canonical source replay remain outside
  the proposal mechanism and cannot be bypassed.

No case ID, family, source hash, target, truth, prior outcome or answer enters
`candidate.py`.

## Generated D0

The frozen run contains 300 cases: `abs` tangency, `min/max` intersection,
coincident shared `piecewise` branch, smooth control and opaque C0 fallback;
each has positive, negative and strict near-miss roles with 20 coefficient
instances.

- complete-set coverage: `220 -> 300`, gain/loss `+80/-0`;
- gains: abs 20, min/max 40, coincident piecewise 20;
- false/extra: 0;
- smooth and opaque activation: 0; baseline results unchanged;
- branch-order, CSE rebuild, variable/residual permutation, equation scale and
  redundant-row metamorphic comparisons: `150/150` agreement;
- tests: 9/9 pass.

The result is mechanism evidence only.  No development145, formal scorer,
holdout, truth, target, HP or CAS input was opened.

## Connection decision

The current product seam exposes conservative branch sensitivity but not the
complete typed active-site identity and adjacent analytic branches for
`abs/min/max/piecewise`.  The historical thin SSA bridge covers `abs` only;
extending it faithfully would require compiler/runtime branch telemetry and is
larger than the 30-minute connection limit.  No shared compiler, worker,
framework or public API is changed.

Reopen connection only when an existing runtime seam supplies, without a
compiler fork, the unordered active-site set, adjacent branch Jacobians and
pointwise branch identity for all four admitted opcodes.  Then run a fresh
equal-work breadth panel before any real/formal screen.
