# EXP-INTERVAL-001 experiment card

## Hypothesis

Some low-dimensional numerical failures have a small, regular root basin that
can be isolated cheaply from the already compiled residual DAG. A strictly
capability-gated Krawczyk lane may turn such a box into a useful local-search
start without weakening exact descriptor authority or starving the numerical
baseline.

This experiment does **not** hypothesize that interval subdivision is a general
replacement for the Python champion. The frozen broad experiment already found
that wider discovery was applicability-limited and added 24.6% work for only
two unrelated generated gains. The current route therefore stays at dimension
one or two, has hard work/time caps, and never promotes its own answer.

## Mechanism

- Compile only a complete expression DAG over constants, variables, addition,
  subtraction, multiplication, negation, integer powers 0--6, and division
  whose denominator interval excludes zero.
- Evaluate the residual and its symbolic forward derivative together with
  outward-expanded binary64 intervals. No finite differences or opaque
  callbacks are accepted.
- Breadth-first split the widest box. Exclude boxes whose residual interval
  omits zero; otherwise try a midpoint-preconditioned Krawczyk operator.
- Emit the enclosure midpoint only when every Krawczyk component is strictly
  inside its source box.
- Mark every emitted point `authority=false`, `requires_local_solver=true`, and
  `requires_canonical_source_replay=true`. The route has no answer insertion
  API and records `answer_promotions=0`.
- Lead every interval launch pair with a baseline launch. With the default
  eight slots, at least two (25%) are reserved for baseline; unused or rejected
  interval slots become baseline slots.

The pure-Python interval implementation is a mechanism probe, not a new trusted
verifier. A survivor should use the production validated numeric capability (or
an audited interval library), but retain this proposal-only authority boundary.

## Truth-blind applicability gate

The gate can inspect only expression capability, dimensions, residual count,
bounds, branch state, guard state, and route budgets:

- `1 <= dimension <= 2` and residual dimension equals variable dimension;
- finite bounds with width at most 4 and volume at most 16;
- a complete `validated-dag`, one stable branch, and every strict guard known to
  be interior on the whole box;
- no transcendental, branch, nonsmooth, unknown, or opaque operation;
- division only when its denominator is separated from zero on the whole box.

Problem ID, family, geometry name, target value, known solution count, scorer,
and prior benchmark outcome are neither represented nor accepted by the gate.
An inapplicable route visits zero discovery boxes and yields all launch slots to
baseline.

## Frozen resource boundary

Defaults are 32 visited boxes, depth 8, 50 ms, four proposals, and two
dimensions. The box cap is checked before each evaluation and the wall-clock cap
before each box. Exceeding either returns partial proposals only; it does not
borrow baseline slots. A numerical interval failure clears route proposals and
falls back safely.

These caps are intentionally much smaller than the frozen discovery prototype's
220 interval-work budget. Higher-dimensional subdivision, black-box interval
extensions, and general transcendental interval evaluation remain closed.

## Generated S0 evidence

The deterministic ten-fixture panel used no formal dataset, scorer, or answer
manifest:

- regular 1-D and coupled regular 2-D: 2/2 produced a Krawczyk proposal;
- singular root, nonsquare nonunique manifold, root on a box boundary, and
  strict-guard boundary: 0/4 produced a proposal;
- transcendental, branch-crossing, and opaque callback: 0 boxes visited and
  full baseline fallback;
- hard cap fixture: exactly 3/3 allowed boxes visited, then `work-cap`;
- answer promotions: 0; minimum-baseline-quota violations: 0.

The mechanism has 13 passing unit tests covering the same contracts plus
outward arithmetic sampling, malformed/overflow fallback, division-domain,
dimension/width/volume/power gates, and a deterministic time cap. Raw aggregate
evidence is in `results/generated-s0.json`.

## Prior evidence and primary references

The design retains the positive one-box boundary from the frozen
`EXP-BROAD-002/c3v` experiment and the 25% IID floor from
`EXP-BROAD-002/interval_discovery`. That earlier discovery lane improved its
generated aggregate from 21/24 to 23/24 targets and safe-full from 5/7 to 6/7,
but consumed 24.6% more work and found only two unrelated gains. This card is a
narrow integration probe, not a reopening of its rejected broad route.

- Krawczyk and Neumaier, “An improved interval Newton operator” (1986),
  existence/uniqueness fixinterval results: <https://doi.org/10.1016/0022-247X(86)90303-3>
- IntervalRootFinding.jl root guarantees (Newton/Krawczyk need
  differentiability; bisection alone does not certify uniqueness):
  <https://juliaintervals.github.io/IntervalRootFinding.jl/stable/roots/>
- IntervalRootFinding.jl branch-and-bound internals, including unknown boxes,
  tolerances, iteration caps, and breadth-first behavior:
  <https://juliaintervals.github.io/IntervalRootFinding.jl/latest/internals/>
- Breiding, Rose, and Timme, Krawczyk interval certification of isolated
  nonsingular square polynomial roots: <https://arxiv.org/abs/2011.05000>
- HomotopyContinuation.jl's official nonsingular solution certification notes:
  <https://www.juliahomotopycontinuation.org/HomotopyContinuation.jl/dev/certification/>

## Integration seam

A Python-champion adapter would translate only a solver residual DAG that can
prove the gate fields. It would pass emitted points into the ordinary start
queue, charge every interval box to the shared callback/work ledger, preserve
the baseline prefix, and leave local validation, HP exactification, descriptor
deduplication, and canonical source replay untouched. If any source operation
cannot be translated exactly, the adapter must return `inapplicable` before
interval work.

## Advance, stop, and reopen gates

Advance to an unscored champion-source adapter only if the benchmark owner can
measure nonzero applicability on source-only metadata and preserve the same
zero-authority contract. Formal S1/S2 measurement belongs exclusively to the
benchmark owner.

Stop on any extra/invalid/crash, a canonical replay bypass, a recurring case
loss, baseline quota violation, or no recall signal with more than 20% search
work. Reopen broader subdivision only with evidence that the earlier 24.6% work
cost is removed and at least two independent families benefit. Reopen
transcendental or opaque evaluation only after a complete validated interval
extension exists; do not approximate it with sampling or finite differences.
