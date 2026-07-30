# Proof-obligation SBFE current connector decision

**STOP_BEFORE_CONNECTOR. No connector or dry/generated integration was
created.**

The current hash-bound composition has sound canonical authority boundaries,
but it does not expose the pre-dispatch proof graph required by the frozen D0.
This is an API/semantics blocker before any case can be classified, so no
problem source, result, development input, scorer, or truth artifact was read.

## Why the current path is not a schedulable OR

`exact_outer._run_exact_outer` unconditionally calls the ordinary HP child
first.  Only after its terminal mapping is returned does it compute remaining
time and launch the exact-coordinate fallback.  In `CONFIRM_ALL_AUTHORITIES`,
an ordinary success is not an independent final route: the exact fallback must
succeed and its descriptor identity must match.  An ordinary failure may be
rescued by that same fallback, but the caller has no pre-work choice between
two proof routes.  This is one fixed sequential compound path, not a public
heterogeneous OR.

The exact child has wall/RSS caps, but it exports no descriptor-bound route
alternatives, shared-prerequisite IDs, predicted route costs, first-service
age, or reveal callback before ordinary work.  Its status and descriptor are
available only after child completion.

## Existing state matrix

| Existing state | Useful state present | Missing SBFE seam |
| --- | --- | --- |
| exact outer | ordinary/exact terminal, exact descriptor check, fixed fallback cap | pre-dispatch OR graph and alternative-route cost |
| HP lock | per-core lease, memory/wall containment, typed post-hoc terminal | proof nodes, shared prerequisite identity, pre-work outcome callback |
| cross-endpoint rungs | immutable endpoint, age, dense-build/dispatch caps, FIFO resume queue | descriptor obligation and more than one backend route per dispatch |
| adaptive exact Wave 2 prototype | coordinate-first and univariate source-link routes | not bound to current exact outer; live breadth child exposes only coordinate route |

The cross-endpoint scheduler calls one `H1No1280RungRunner` per FIFO endpoint.
Its `RungRequest` has source/endpoint/restart/deadline state, not a descriptor or
route.  Charged cost and terminal outcome are recorded after the runner
returns.  Reordering these rungs, cache entries, or species would only change
an existing scheduler and is explicitly excluded.

## Budget and authority custody

The current progressive shim preserves 25% original-order search handoff and
25% counter-Cauchy insurance.  That is not a completed, byte-identical final
authority queue receiving at least 75% of total budget and first service.  No
post-baseline hook can prove that an SBFE graph lane consumes at most 25% and
returns unused budget without altering already successful descriptor work.

The downstream pieces that must remain unchanged do pass static audit:

- `exact_outer` remains the only positive-dimensional descriptor emission
  boundary and never treats the ordinary numeric descriptor as final;
- champion-v2's source-exact zero-dimensional object and route retain identity;
- a scheduler would not emit authority directly.

Zero-dimensional authority is deliberately excluded from activation strata.
With no current callable heterogeneous OR, static activation is `0` anonymous
positive-dimensional strata, below the required `2`.

## Reopen gate

Reopen only when the current callable worker supplies all of the following
before doing proof work:

1. descriptor-bound monotone obligations with at least two genuinely
   available heterogeneous routes, stable shared-prerequisite IDs, declared
   route caps/costs, and typed reveal callbacks;
2. a completed byte-identical authority baseline with first service under at
   least 75% budget, followed by a graph lane capped at 25% with unused budget
   returned;
3. truth/source-outcome-independent activation on at least two anonymous
   positive-dimensional structural strata;
4. authority emission only through the unchanged canonical source/guard/
   branch/raw-target replay and exact-outer workers, with the zero-dimensional
   route identity-bypassed.

No formal execution, development run, scorer, truth, or CPUs 0--13 were used.
The source audit and tests ran only on CPU15 with one native thread.

