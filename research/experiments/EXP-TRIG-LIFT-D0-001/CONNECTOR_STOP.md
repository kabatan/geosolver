# Truth-blind source seam audit: connector stop

## Decision

```text
source-surface census: COMPLETE
existing compiler intersection: ZERO for D0-compatible trig
all-real-root completeness gate: NOT SATISFIED
disposable connector implementation: PRE-CODE STOP
real solver / scorer / validation / sealed execution: NOT RUN
```

The source surface is nonempty, but the requested existing end-to-end seam is
not. Development145 contains nine formulations accepted by the deliberately
narrow trig recognizer. None of those nine is accepted by the existing
semantic-cover + bounded-reducer polynomial backend. Independently, that
backend's completed numerical path transcript is an exposure gate, not a
mathematical guarantee that every isolated source root was enumerated.

Either limb is sufficient to stop the connector. Both fired.

## Custody

The input was the frozen development-only container with SHA-256
`c150bb35...a8511`. The scanner lexically sliced only each top-level
`formulation` value. Full rows and sibling values were never deserialized;
problem IDs were neither retained nor reported. The source target AST was read
only to reject raw phase-variable escapes. No truth, scorer, expected value,
historical result, validation or sealed formulation was read.

The audit emitted aggregate counts only. It did not retain case digests,
expressions or per-case records.

## Static activation

| source-only predicate | cases / 145 |
|---|---:|
| any Distance occurrence in a constraint | 126 |
| sound direct `Distance == positive rational/Distance` square | 113 |
| `PointOnCircle` with exact-affine phase | 16 |
| explicit exact same-phase `sin` + `cos` pair | 6 |
| union of exact-affine trig forms | 21 |
| finite-sheet, single-phase, no-escape D0 trig | 9 |
| D0 trig plus sound Distance square | 7 |

There are 183 direct Distance-to-positive-rational constraints and 53 direct
Distance-to-Distance constraints. Counts may overlap within one formulation.
The 13-case gap between any Distance constraint and safe Distance-square cases
is deliberate fail-closed behavior for nested or otherwise unsupported
equalities.

These are syntax/operator activation counts, not polynomial-block eligibility,
root counts, solved counts or recall evidence.

## Existing compiler/backend intersection

The read-only static call path was:

```text
EXP-REAL61-002/algebraic_lane/compiler.py
  -> EXP-REAL61-004/polynomial_homotopy_proposal/reducer.py
  -> eligible_polynomial_homotopy_revisit.compile_source
```

It evaluated no target graph and invoked no root worker or source replay.

| existing static seam | cases / 145 |
|---|---:|
| bounded polynomial backend eligible | 8 |
| eligible and broad exact-affine trig | 1 |
| eligible and D0-compatible trig | **0** |
| eligible and safe Distance square | 7 |
| eligible and D0 trig + Distance | **0** |

The single broad-trig intersection fails at least one of the D0 obligations
(finite single phase and no raw escape). It cannot be routed to the prototype.
The seven Distance-only intersections do not create a trig connector; the
existing semantic compiler already owns their algebraic representation.

## Mandatory overlap and completeness audit

- `semantic_algebraic_lift` directly owns same-phase unit-circle lifting,
  rational harmonics, finite `atan2` ledgers and mandatory replay. It stops
  before a joint root solver.
- `eligible_polynomial_homotopy_revisit` owns the exact source compiler,
  bounded reducer, all-start-path transcript gate, coordinate reconstruction
  and untouched source replay. Its card explicitly states that numerical
  completion of all paths is not mathematical proof that every isolated real
  source root was found.
- `certified_polynomial_lane` has the same completeness limitation and its
  direct source applicability result is already terminal negative evidence.
- The exact Sturm/guarded regular-chain composition is already recorded by
  `wave14_sturm_source_coordinate_proposal` and
  `wave12_triangular_exact_coordinate_proposal` as a terminal exact-mechanism
  duplicate. Repackaging its root isolator behind this lift would be backend
  placement, not a new mechanism.
- The D0 `numpy.polyroots` stereographic solver is proposal-only and also makes
  no multiple-root or all-root completeness claim.

Relevant frozen hashes:

```text
semantic lift compiler                 4ab15c79...9836
semantic lift card                     e9720256...ba1d
source polynomial compiler             f127f7f1...0318
bounded reducer                        39ef2316...10e8
source homotopy candidate              37641aff...8c49
source homotopy card                   1255ccb2...a681
Sturm duplicate card                   cc8ad1f2...111b
triangular duplicate card              e4e76ce6...6ab0
mechanical algebra duplicate decision  e4585fab...f9c2
```

## Why no connector was written

The requested condition was an existing tiny backend that could enumerate all
roots and return them to canonical replay. The closest existing source seam has
zero D0-compatible inputs and lacks the required completeness guarantee.
Writing a connector would therefore be dead code on the frozen development
source, while substituting a new exact compiler/backend would violate the
no-infrastructure/no-refactor scope and reopen terminal exact lineages.

No connector, backend wrapper, source compiler, root worker or shared solver
change was created.

## Reopen gate

Reopen only when all conditions hold:

1. the unchanged source compiler admits at least three D0-compatible trig
   formulations across at least two anonymous structural signatures;
2. an existing bounded backend supplies a checkable complete enumeration of
   every supported real branch, including multiplicity/singular/pole and
   exceptional strata, rather than merely completing numerical start paths;
3. its reconstruction already reaches the untouched canonical source replay
   with strict bounds, guards, selectors, branch and ordinal obligations;
4. the composition is not a frozen Sturm/regular-chain/homotopy/quotient-
   algebra backend-placement duplicate.

Distance-only lowering should be evaluated through the existing semantic
compiler lane, not used to disguise the zero trig intersection.
