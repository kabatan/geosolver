# EXP-LOCAL-001 — diagnostic pilot closure

`EXP-LOCAL-001` is closed without a formal algorithm decision.  Its committed
six-case, eight-start run was explicitly labelled a diagnostic pilot and is not
eligible to select a scaling policy, authorize locked validation, or change the
product solver.

The original card, pilot runner, CSV and report are preserved and hash-bound by
[`pilot-closure.json`](../../research/experiments/EXP-LOCAL-001/pilot-closure.json).
There is no 48-case development input freeze, independent formal assessor,
formal run, locked input or product connection.  The compact governance state
is recorded in [`summary.json`](../../research/results/EXP-LOCAL-001/summary.json).

The pilot remains useful only as a prior and a source of counterexamples.  In
particular, a residual-qualified local endpoint is not thereby a correct
configuration or target answer.  None of the pilot's numerical observations is
promoted to current evidence.

The present Core and DSL have diverged materially from the card's historical
control: semantic variable/residual scales are already used, finite-difference
coloring exists, while analytic/ForwardDiff providers and sparse CPQR do not
form the declared production route.  Replacing those assumptions after seeing
the pilot would no longer be a prospective test of the original card.

The current-core question therefore moves to `EXP-LOCAL-003`, which must be
preregistered before generator or mechanism source, use fresh result-blind
inputs, retain open-plugin/C0 fallback behavior, and keep canonical semantics
separate from any algorithmic scaling.
