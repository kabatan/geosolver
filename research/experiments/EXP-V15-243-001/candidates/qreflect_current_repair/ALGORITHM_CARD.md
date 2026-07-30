# Exact QPoint/QPoint qreflect current repair

## Hypothesis and mechanism

The current exact-coordinate QQBar replay already implements line reflection
as `qreflect(QPoint, QLine)`, but has no dispatch for the closed direct source
construction `Reflect(point, center_point)`.  The missing exact operation is
the affine involution

`qreflect(value::QPoint, center::QPoint) = 2 * center - value`.

This disposable candidate directly copies the current exact-coordinate
candidate, fallback, QQBar worker, and DAG compiler.  Its only semantic change
is the QPoint/QPoint method above.  The QPoint/QLine method and every existing
dispatch remain byte-identical.  The source compiler, guard and branch replay,
raw target link, minimal polynomial, real-root ordinal, isolator, numeric
precision lanes, and canonical authority consumer are unchanged.

The root-provided truth-blind applicability aggregate was 16 missing-dispatch
attempts across two anonymous sources.  No individual source, answer, case ID,
family, truth, or score was inspected here.

## Truth-blind portfolio connection

The candidate imports and hash-verifies the current exact outer at
`05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7`,
captures its installed HP callable once, and runs it first with at least 75%
of the endpoint allocation.  The side lane is capped at 25% and is eligible
only when all of these conditions hold:

1. source bytes match the supplied SHA-256;
2. the source construction is a sequential list containing a statically
   closed, direct `Reflect(P,C)` whose two bare-name operands were previously
   constructed by direct `Point(scalar,scalar)` calls;
3. every encountered Reflect rejects unknown/mixed/list/selector/nested/
   keyword/wrong-arity forms;
4. the baseline's own exact-coordinate artifact matches source and endpoint
   hashes and failed specifically with missing `qreflect(QPoint,QPoint)` Julia
   dispatch;
5. endpoint dimension is nonzero.

Current authority or resource-busy results are returned by identity.  A side
timeout, failure, containment mismatch, or canonical replay rejection also
returns the exact baseline mapping object by identity without telemetry
mutation.  Success nests that baseline and must pass the unchanged current
`_consume_fallback` canonical boundary.  Numerical search always retains the
baseline allocation.

## Fixed direct-copy provenance

Unmodified current source hashes before patching:

- exact candidate: `e0f24e605e7e7211d134ddea66e66adbb89307148a8f03c1afebd4a2c969c66f`
- fallback worker: `44d6fa802dc51e7f58e5a72e48b434a62be84275c328bd605f0e9e2f6eb11900`
- QQBar worker: `3ac6415600da77f8748a11d15fa47eb3dcb9f8deada375388fc762a155df0b4a`
- DAG compiler: `9b83181004a8ea2ea73f2974129e37ce252f7d352937b9f8b601b39eddf03d18`

Modified closure hashes:

- worker: `e48d7b5f7d85b0beaf74cce6e918275c18d6d67bc6522907bfdd3b0d586cd545`
- fallback worker: `8bb2f24dfac23b5ed3898ad69ebafd644a6d20168cee4d4131297899d16f1da6`
- candidate: `93335b86559c76893373f6a418953a6dc4663ff01bb3533c615d5f2f1e5367ff`
- QQBar worker: `482b093772cec9c6f2d9cde1bbd3dd6c664f552a89fda70a12550928799b0a76`
- DAG compiler: `9b83181004a8ea2ea73f2974129e37ce252f7d352937b9f8b601b39eddf03d18`
- framed five-file mechanism hash:
  `e311100d579bb1aabdf63676d070351ee542f784132dbed735de00b79209436b`

## Generated D0 evidence

Under the current Python/Julia closure pinned to CPU 14 (CPU 15 was reserved
by the benchmark owner during this run):

- exact QPoint/QPoint replay: 5/5, covering integer, rational, argument order,
  translation, rotation/reflection-style affine variants;
- the unmodified current replay rejects the same generated point construction
  with the expected missing `qreflect(QPoint,QPoint)` dispatch;
- local and current QPoint/QLine replay: 2/2;
- generated full worker source with the one QPoint/QPoint overload removed is
  byte-identical to current, proving existing line dispatch preservation;
- source classifier: positive direct/chained cases 2/2; point-line, unknown,
  list, selector, nested call, keyword, and arity cases rejected 7/7;
- ready, zero-dimensional, side-failure, and side-crash paths return baseline
  by identity;
- actual guarded side replay passed the current canonical consumer with same
  process group, PDEATHSIG 9, and CPU affinity `[14]`;
- side allocation was no more than 25%.

Disposition: `D0_GO_QREFLECT_CURRENT_REPAIR`.  Formal/corpus/manifest/result/
scorer/truth interfaces were not used.  Benchmark owner controls applicability
and formal evaluation.
