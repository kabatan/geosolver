# EXACT_TYPED_ANGLE_EQUALITY Repair A

## Hypothesis and mechanism

The frozen QQBar replay represents an unsigned point Angle as an exact
`AngleExpression` in `[0,pi]`.  Compiling a source constraint as subtraction
can ask the later zero test to reason about full-turn lifts even when the
source relation is a direct, same-typed `Angle(...) = Angle(...)` in an
injective principal domain.

Repair A is a disposable direct copy of the current exact-coordinate closure.
The copied DAG compiler recognizes only a bare `Angle` call on both sides of a
source constraint, with equal arity two or three and no keyword arguments.  It
emits `typed_angle_eq` rather than scalar subtraction.  The copied QQBar replay
then proves:

- point Angle: exact normalized cosine/sine in `[0,pi]`;
- line Angle: exact absolute normalized dot/cross in `[0,pi/2]`;
- equal source arity and exact principal-domain bounds;
- exact equality of both normalized components.

Every existing coordinate descriptor, source constraint, guard, bound,
branch/selector lowering, raw answer, target descriptor, square-free minimal
polynomial, root ordinal, isolator, numeric replay, and canonical outer-boundary
check remains in force.  qreflect is not used.

## Portfolio connection

The candidate-private outer is a direct copy of current formal-control
`exact_outer_decorator/worker.py` (source SHA-256
`05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7`).
It always runs and retains the unchanged current exact route first with 75% of
the endpoint budget.  The modified direct-copy replay is attempted only when:

1. the source SHA matches;
2. a direct same-arity Angle relation exists;
3. the current exact artifact failed specifically with
   `angle equality has ambiguous full-turn lift`;
4. the endpoint dimension is nonzero.

The side lane is capped at 25%.  A side timeout, crash, containment failure,
near-miss, incomplete ledger, or rejected authority returns the exact baseline
mapping object by identity and attaches no telemetry.  A side success nests the
baseline result and is accepted only through the unchanged canonical boundary.

## Fixed provenance

Unmodified source copies before patching:

- exact candidate: `e0f24e605e7e7211d134ddea66e66adbb89307148a8f03c1afebd4a2c969c66f`
- fallback worker: `44d6fa802dc51e7f58e5a72e48b434a62be84275c328bd605f0e9e2f6eb11900`
- QQBar worker: `3ac6415600da77f8748a11d15fa47eb3dcb9f8deada375388fc762a155df0b4a`
- DAG compiler: `9b83181004a8ea2ea73f2974129e37ce252f7d352937b9f8b601b39eddf03d18`
- authority boundary: `a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9`

The baseline current closure is still hash-verified by the copied outer.

## D0

On Python 3.12.11, SymPy 1.14.0, mpmath 1.3.0, Julia/Nemo from current
formal-control, pinned to CPU15:

- full exact replay positives: 3/3 (point, reflected point, line);
- supplementary/degenerate near-miss rejection: 2/2;
- full modified fallback and unchanged outer boundary: authority pass;
- current-result identity on missing artifact, side failure, and zero dimension:
  3/3;
- 20-second synthetic budget: baseline 15 seconds, side cap 5 seconds;
- same PGID, PDEATHSIG 9, CPU affinity `[15]`, no containment breach or
  descendant leak.

Disposition: `D0_GO_REPAIR_A`; root owns source activation and formal
benchmarking.  No corpus, scorer, truth, manifest, result, or formal benchmark
was used.
