# EXP-STRUCT-001 result card

Status: **S0 prototype; not production-authorized**.

## Hypothesis and changed axis

A perfect-matched residual-variable graph with multiple irreducible SCC blocks
can reduce local linear-algebra cost and expose lower-dimensional solve stages.
Only structure routing changes. Proposal coverage, source residuals, guards,
targets, and canonical verification remain authoritative and unchanged.

## Controls and candidate

- `DENSE-BASELINE`: all variables and relations are solved together.
- `BTF-SCC-CANDIDATE`: square perfect-matchable systems are solved in SCC
  condensation order; at least 50% of portfolio starts remain dense baseline.
- `IRREDUCIBLE-CONTROL`: a cycle forms one SCC and must route 100% to baseline.
- Non-square, constant-relation, structurally singular, or parse-unsupported
  systems also route 100% to baseline.

Routing consumes only dimension and residual-variable support. It cannot use a
case ID, geometry family, target, answer, or prior scored outcome. A block
endpoint is a proposal only and must pass the same caller-supplied canonical
verifier as the dense endpoint.

## S0 result

On 32 deterministic starts of an eight-variable generated triangular nonlinear
system, dense and block arms both produced 32 canonically accepted endpoints.
The block arm used 529 versus 83,456 cubic linear-work units, but 1,846 versus
1,662 full residual evaluations. Therefore the mechanism has a strong
factorization-cost signal but no oracle-work promotion claim.

Static formulation-only analysis of development145 activated on 27/145
(18.62%) inputs. Applicable systems had mean structural factor-work ratio
0.301. Of all inputs, 111 were irreducible, six non-square, and one unsupported
zero-variable formulation failed closed. The conservative scalar-polynomial
detector activated on zero inputs, so no polynomial side route is proposed.

## Decision and reopen gate

Retain as an applicability-limited prototype. The next experiment must attach
the plan to the common compiled runner and measure evaluator work and wall time
on development inputs. Promote only if canonical exact-set safety remains
perfect and either wall/CPU improves materially or the staged route raises root
capture. Kill unconditional staged evaluation if its observed callback overhead
dominates factorization savings; retain the detector for sparse/AD or block
Jacobian factorization experiments.

## Frozen champion integration seam

The second prototype commit adds `worker.py`, `champion_overlay.py`, and the
common `arm.json`. An applicable dry run verifies the frozen champion closure,
retains all baseline starts, and seals the intended injection point immediately
before the original `_fresh_replay_candidates` source replay. Unit tests pass a
generated block endpoint through a fake original replay and prove that the
overlay itself cannot accept it. A non-applicable dry fixture produced exactly
the same 155,729 PLAN bytes and stdout as direct frozen-champion execution.

Applicable execution remains disabled: the pure-Python S0 block solver incurred
11.1% more full residual evaluations, so binding it to the formal worker before
callback/wall admission would turn a structural signal into an unqualified
algorithm change. The adapter is integration-ready once a concrete proposal
factory meets that gate; no heavy screen was run here.
