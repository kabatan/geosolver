# Proof-obligation SBFE scheduler D0

## Scope and decision

**Decision: GO at generated D0 only.**  This is a disposable, truth-blind
scheduler experiment.  It does not authorize a current-solver connector or a
formal/development run.  The existing connector audit remains authoritative:
integration must wait for a real proof-obligation seam exposing test graph,
estimated costs, reusable node identity, and a final canonical authority call.

No formal case, development source, scorer, answer, validation/sealed artifact,
or CPU 0--13 was read.  All executions were pinned to CPU15 with one native
thread.  The only corpus signal used was the benchmark owner's aggregate-only
observation that `NOT_RUN` is common among missing-safe cases but usually
coexists with an observed exact rejection.  Therefore this D0 requires gains
in full 1-certificates; reducing `NOT_RUN` alone is explicitly a HOLD.

## Hypothesis and reopen gate

A final descriptor is naturally a monotone Boolean proof obligation.  FIFO can
spend the entire surplus budget on one expensive route even when a cheaper
route, a cheap rejecting capability test, or shared proof prefix would resolve
more descriptors.  Reopen scheduling only if a truth-blind cost/probability
policy increases complete certificates in at least two independent positive
generated families without losing one in any positive, negative, or malformed
family.

The generated priors, advertised costs, realised costs, outcomes, budget, and
aging constants were frozen before the first full D0 execution in
`tapes.json`, SHA-256
`07e220eb15c74f525aaadde7fa856f17ba4e59be5a871dbd49b61d665c628d4d`.
They were not tuned after observing the run.

## Frozen mechanism

- Final authority is represented as a monotone AND/OR DAG.  Equivalent DNF
  routes are canonicalized only for scheduling; emitted authority still needs
  a downstream canonical verifier in any future connector.
- Within an unresolved AND route, tests use increasing `c/(1-p)`.  An OR term
  uses `e/q`, where `e` is the expected early-stopping cost under that AND
  order and `q` is its prior success probability.
- Cross-descriptor arbitration applies descriptor first-service aging (10% per
  turn, capped at eight turns) plus a 20% first-service bonus.
- A resolved leaf is shared by every route that references the same public
  node.  No shared test is executed twice.
- The scheduler sees public prior and advertised expected cost.  The realised
  Boolean outcome and realised cost live only in the oracle closure and become
  visible after selection.  An unexpectedly late result consumes the graph
  cap but cannot certify anything.
- The baseline queue is emitted first and is byte-identical between control and
  candidate.  Exactly 75% of total budget is reserved for it, the proof graph
  may consume at most 25%, and unused graph budget is returned rather than
  expanding the side route.

The single-variable `c/(1-p)` rule and route-level stochastic Boolean function
view follow Deshpande, Hellerstein, and Kletenik's SBFE formulation
([arXiv:1303.0726](https://arxiv.org/abs/1303.0726)).  Adaptivity can materially
change evaluation cost in general SBFE
([arXiv:2208.03810](https://arxiv.org/abs/2208.03810)).  D0's local `e/q` plus
aging policy is a heuristic extension to shared arbitrary AND/OR DAGs; this
card does **not** claim global optimality for that general case.

## Precommitted generated tapes

| Tape | Obligation stressed | FIFO failure mode |
| --- | --- | --- |
| P1 | starvation / first service | one long failing AND consumes 24/25 |
| P2 | alternate route | first OR route fails before the cheap route runs |
| P3 | shared prefix | blocker hides three certificates sharing one node |
| P4 | cheap capability reject | expensive leaf precedes a cheap false capability |
| N1 | FIFO already optimal | candidate must tie |
| N2 | all routes fail | candidate must not invent authority |
| M1 | partial proof | true prefix without full witness must not certify |
| M2 | deadline-late | late outcome must not enter resolved state |

Metamorphic checks cover leaf/descriptor ID renaming, mapping and child
insertion permutation, common cost+budget scaling, equivalent DAG factoring,
and adding an inert false terminal route.  Forty of forty checks pass.

## D0 result

CPU15 / Python 3.12.11, generated-only:

- full 1-certificates: control `2`, candidate `9`;
- positive families improved: `4/4`; losses across all P/N/M tapes: `0`;
- false authority: `0`; baseline 75% byte contract: `8/8`;
- descriptor first service: `10 -> 16` (`+60%`);
- `NOT_RUN`: `16 -> 12` (`-25%`);
- shared-prefix tape: one execution of the shared leaf served three additional
  canonical route occurrences;
- measured scheduler overhead: `0.68%` relative to generated realised work
  under the precommitted one-cost-unit = 1 ms convention, below the 20% D0
  ceiling.  This is a mechanism-screen number, not a production speed claim.

All hard GO gates pass.  If only the `NOT_RUN` metric had improved, the frozen
decision rule would have returned `HOLD_NOT_RUN_ONLY`.

## Failure taxonomy and next gate

D0 directly covers starvation, bad OR route order, duplicated shared work,
capability-test inversion, partial witness, all-fail, and late-result authority.
It does not establish calibration on real graph nodes, graph extraction cost,
or recall on geometry cases.  A future connector may proceed only when the
current solver exposes complete public proof obligations without taking budget
from already successful descriptors, preserves the 75% byte-identical baseline
queue, and returns every emitted descriptor through canonical source replay.
Priors/costs must then be calibrated from generated data once, frozen, and
owned by the benchmark agent; no per-case or truth-driven tuning is allowed.

