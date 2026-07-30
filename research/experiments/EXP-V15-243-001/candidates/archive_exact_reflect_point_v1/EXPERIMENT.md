# Exact `Reflect(point, point)` replay shim

## Hypothesis

The exact-coordinate fallback rejects otherwise replayable sources containing
`Reflect(point, point)` because its frozen QQBar evaluator implements only
`qreflect(::QPoint, ::QLine)`.  The typed numeric and analytic-AD evaluators
both define the two-point form as `Reflect(reflected_point, center) =
2*center-reflected_point`.  Adding that exact typed opcode should recover this
source stratum without changing search, recognition, or authority policy.

The source-only construction census found seven point-reflection appearances;
the aggregate control fallback ledger recorded sixteen rejected attempts with
the missing `qreflect(::QPoint, ::QPoint)` dispatch signature.  These counts
motivate activation only; no case identity or outcome is exposed to routing.

## Mechanism and safety boundary

The private candidate inserts one Julia method,
`qreflect(::QPoint, ::QPoint)`, immediately after the unchanged line method.
Removing that method restores the original extended worker byte for byte.
Point reflection uses no division, selector, branch, guard, or degeneracy
condition.  Unsupported argument types still fail closed through Julia typed
dispatch.  The existing degree-eight independent recognition, exact source,
relation, guard, branch, bound, raw-target replay, root-ordinal attestation,
and global `CONFIRM_ALL_AUTHORITIES` boundary are delegated unchanged.

The archive exact-only worker, scheduler, zero-dimensional authority, and raw
QQBar worker remain hash-pinned.  The archive outer's candidate and fallback
paths alone are rebound to private wrappers.  There is no problem, family,
truth, expected-count, target-value, or prior-outcome routing.

For formal containment, this candidate directly copies the reviewed
`ec10e4ed` same-group lifecycle and `sitecustomize` propagation bytes into its
own directory.  Only `BASE.run_guarded` and the child bootstrap environment
are replaced.  Commands, resource limits, time budgets, native-thread values,
search/HP algorithms, descriptor acceptance, and authority policy remain with
the historical caller.  The worker root never creates a new process group or
session; the inherited formal deadline and exact-parent death signal apply to
all candidate children.

## D0 and promotion gate

Generated exact tests cover integer and rational positives, wrong target,
wrong type, argument reversal, affine/rotation/reflection images, exact line
reflection differential equality, overload removal equality, hash custody,
and source-only PLAN binding.  Formal execution, scorer data, and real-case
outcomes are intentionally left to the benchmark owner.

Promote only if the common benchmark shows recurring safe recall on at least
two independent clusters without extra/invalid/crash.  Reopen only if a later
failure shows a different missing typed algebraic opcode or demonstrates that
point reflection has an unmodeled semantic guard.
