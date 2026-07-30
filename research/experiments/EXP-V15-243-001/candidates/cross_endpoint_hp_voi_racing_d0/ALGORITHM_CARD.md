# Censor-aware cross-endpoint HP VOI racing — D0

## Hypothesis

The previous cross-endpoint FIFO experiments established that breadth can find
complementary descriptors, but their real transfer either lost as many cases
as it gained or failed to return descriptors.  A retry lane should therefore
be chosen using value of information from an ordinary/low-precision rung,
without sacrificing the broad first-probe insurance that protects unknown
families.

## Mechanism

The scheduler freezes a four-slot cycle:

1. three equal-cost first probes of content-key-ordered untried endpoints;
2. one equal-cost HP restart selected across all observed endpoints.

Thus at least 75% of wall and callback work is spent on untried endpoints
while they remain.  The first retry is the residual-best baseline insurance.
Later retry scores use only:

- ordinary/low-precision residual improvement rate;
- repeat stability;
- anonymous descriptor-hint novelty;
- that endpoint's completed/censored counts;
- the declared full-restart cost.

Every restart is charged at its complete registered wall/callback cap.
Censoring is retention evidence, not terminal failure: it reduces the
optimistic survival term but never permanently suppresses an endpoint.
Acquiring one descriptor does not stop cross-endpoint exploration.  Exact
descriptors are admitted only with both authority-contract and original-source
replay booleans.  Cheap hints can rank work but can never become output.

The mechanism is not a PSLQ grid, precision-path reordering, UCB over case
history, or target-value heuristic.  It receives no case ID, family, truth,
known target count, or previous-case outcome.

## Prospective D0 gate

Four generated opaque structures are frozen:

- duplicate-heavy endpoint reservoirs;
- one hard novel endpoint among easy duplicates;
- a misleading cheap-rung decoy whose HP work is censored;
- all-fail/opaque backends.

Control and candidate receive identical wall and callback caps.  Required
gates are loss/false/extra zero, gains in at least two structures, exact 75%
first-probe insurance, endpoint-permutation invariance, censor-prefix
invariance, full restart charging, and fail-closed malformed outcomes.

## Prior evidence and reopen boundary

- `cross_endpoint_hp_rungs` was stopped because its H1 authority did not prove
  a guarded source root; none of that authority is reused.
- stateless breadth real G3 was `+5/-5` and stopped at net zero.
- the callback-hazard UCB lineage allowed a decoy to starve a root lane; this
  candidate has no unconstrained UCB and retains the fixed 75% insurance.
- the current H1 cap-hit signal is too weak to justify VOI ranking.  Even if D0
  passes, live integration is forbidden until a candidate-private bridge can
  honestly expose improvement, stability and anonymous novelty milestones.

This is a generated D0 only.  It does not invoke HP backends, scorer, benchmark
truth, validation, sealed data, or the shared scheduler/framework.
