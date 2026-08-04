# DSL deficiency audit and source-faithful repairs (2026-08-05)

This audit was performed on the `experiment` branch before rerunning the
solver.  The source statements and answer expressions were not changed.  The
repairs only restore conditions that are stated in the source problem but were
missing or represented with the wrong predicate.

## Repairs

### Interior predicates

`Area(A,B,P)>0` is an unsigned-area predicate in the runtime, so it does not
mean that `P` is on the prescribed side of the edge.  For triangles, the
repairs use the three signed cross products for the source vertex order.  For
convex quadrilaterals, the repairs use `AssumeConvex` and pairwise products of
the edge-side signs, so the formula is independent of whether the coordinate
gauge is clockwise or counterclockwise.

| case | source clause restored |
|---|---|
| AIME-2007-II-15 | the radius-`r` disk and its center are interior to `ABC` |
| AIME-2023-I-12 | `P` is inside equilateral `ABC` |
| AIME-2025-II-14 | both `K` and `L` are inside right triangle `ABC` |
| HMMT-2022-FEB-GEO-10 | `P` is inside convex quadrilateral `ABCD` |
| HMMT-2025-FEB-GEO-01 | `D` is inside triangle `ABC` |
| JMO-2006-PRE-09 | `O` is inside triangle `ABC` |
| JMO-2010-PRE-08 | `P` is inside triangle `ABC` |
| JMO-2020-PRE-02 | `H` is inside regular hexagon `ABCDEF` |
| JMO-2021-PRE-03 | `P` is inside triangle `ABC` |
| JMO-2021-PRE-10 | `P` is inside quadrilateral `DBCE`; convexity is explicit |
| JMO-2022-PRE-04 | `P` is inside convex quadrilateral `ABCD`; convexity is explicit |

### Segment/order predicates

The following cases had a collinearity or coordinate parameter but did not
fully enforce the source's segment or point-order clause.  `OnSegment` was
added; endpoint exclusions stated in Japanese were kept as strict positive
distance guards.

| case | source clause restored |
|---|---|
| HMMT-2008-FEB-GEO-10 | `D` on `BC`, `C` on segment `AE`, and `B` on segment `AF` |
| JMO-2010-PRE-11 | `P` on segment `MN` |
| JMO-2016-PRE-05 | `P` on segment `CD` |
| JMO-2017-PRE-10 | `Q` on segment `CA` |
| JMO-2018-PRE-06 | exact official-image order `A,Y,X`, `B,Z,Y`, `C,X,Z`; all three points are interior |
| JMO-2019-PRE-10 | ordered intersections `B,F,G,C` on segment `BC` |
| JMO-2023-PRE-10 | `P` on segment `BM` |
| JMO-2024-PRE-03 | second intersections `D` and `E` on sides `AB` and `AC` |
| JMO-2024-PRE-06 | `E` on `BC`, excluding both endpoints |
| JMO-2024-PRE-09 | angle-bisector intersection `E` on side `BC` |

### Cyclic-order and free-variable cleanup

Two cyclic-quadrilateral definitions did not explicitly select the named
quadrilateral branch.  `AssumeConvex([M,A,R,E])` was added to HMMT-2018-FEB-GEO-05
and `AssumeConvex([A,B,C,D])` to JMO-2024-PRE-09.  The latter also contained an
unused free variable `b`, and JMO-2017-PRE-10 contained an unused `q`; both were
removed.  These removals do not alter any source condition—they remove only
variables that occurred nowhere in the construction, constraints, guards, or
answer.

The JMO-2018-PRE-06 repair is especially important: the official problem
image says “A,Y,X; B,Z,Y; C,X,Z” in that order.  The previous JSON fixed
`X` to `AC` and used `Z` beyond `C`, which was a different problem.  The
repaired JSON uses six free coordinates for `X,Y,Z`, the three collinearities,
the three ordered `OnSegment` constraints, and strict interior guards.

## Integrity checks

After the repairs (22 DSL files touched, counting the cyclic-order repair):

* `validate_dataset.py`: 548 source rows, 296 unique scope records, 302 DSL
  files, 279 runnable unique cases, 17 reference-only files.
* `verify_dsl_integrity.py --benchmark benchmark_results_180s_1core_final.json`:
  `errors=0`; source hashes, manual-audit rows, truth rows, duplicate keys,
  IR parsing, and the 0–7 free-variable limit all pass.
* `runtime_api_compat_regression.py`: PASS.
* `git diff --check`: PASS.

The solver benchmark is run separately after this audit, using only the
modified cases and the frozen runtime (180 seconds, one core, seed 7).

## Focused benchmark

The first run is
`benchmark_results_180s_1core_dsl_deficiency_repairs_2026-08-05.json` (21
cases).  The later cyclic-order/free-variable additions are in
`benchmark_results_180s_1core_dsl_deficiency_repairs_2026-08-05_v2.json` (3
cases; the v2 rows supersede the duplicate JMO-2017-PRE-10 and
JMO-2024-PRE-09 rows from the first run).

The verified-truth rows in the focused run are:

| case | result |
|---|---|
| AIME-2007-II-15 | exact set match: `260/129` |
| AIME-2023-I-12 | exact set match: `75` |
| AIME-2025-II-14 | exact set match: `104*sqrt(3)` |
| HMMT-2008-FEB-GEO-10 | exact set match: `2014024` |
| HMMT-2025-FEB-GEO-01 | exact set match: `26` |
| JMO-2006-PRE-09 | exact set match: `7*sqrt(3)/3` |
| JMO-2019-PRE-10 | exact set match: `(-3+sqrt(33))/6` |
| JMO-2022-PRE-04 | exact set match: `245/6` |
| HMMT-2018-FEB-GEO-05 (v2) | expected root `8*sqrt(2)/9` found, plus an extra near-zero root; this is a solver-side boundary false positive, not a DSL branch |

The other 13 unique modified cases have `truth_status=unresolved` (or are a
timeout/no-solution run), so the benchmark intentionally does not label them
correct or incorrect.  The focused runs had no solver exceptions.  The
HMMT-2022-FEB-GEO-10 case timed out at 180 seconds; JMO-2024-PRE-06 remained
`no_solution`, as it already was in the prior frozen benchmark.  JMO-2017-PRE-10
timed out in the v2 rerun after removing its unused variable.  These outcomes
are reported separately from DSL fidelity.
