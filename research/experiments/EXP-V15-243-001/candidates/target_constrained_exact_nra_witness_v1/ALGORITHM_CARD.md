# TARGET_CONSTRAINED_EXACT_NRA_WITNESS — D0 card

Hypothesis: many exact rejections are caused by proving a target relation
without proving that the proposed target cell has an exact source witness.
Query the complete real-polynomial formula

`exists source_coordinates,t: source ∧ t=raw_target ∧ p(t)=0 ∧ l<t<u`

and accept only after reconstructing every model coordinate from exact
Rational/AlgebraicNumRef data and independently replaying the untouched source
equations, typed Boolean guard, all division definedness, raw target, proposal
polynomial, real-root ordinal and isolator.

Reopen gate: archive completeness candidate 07 (CAD/Redlog) was a proposal,
never implemented. Current formal aggregate has 46 source-valid misses and 41
exact-rejection cases: no relation 20, contract 11, timeout 10. This candidate
tests the missing target-constrained witness mechanism rather than reopening a
generic polynomial backend/path-order experiment.

Preferred backend was Z3 complete QF_NRA with exact AlgebraicNumRef model
extraction. The frozen Python and host have no `z3`, Redlog, QEPCAD, Singular,
Sage, or Reduce executable/module. No dependency was installed. The disposable
fallback admits only a subset for which SymPy is complete: a zero-dimensional
QQ equality variety exhaustively enumerated by Gröbner/`solve_poly_system`, plus
declared coordinates absent from equations, guards, definedness and target.
Relevant positive-dimensional fibers, UNKNOWN, timeout, unsupported operators,
transcendentals and undecidable exact signs are `NOT_PROVED`.

R1 frontend reuse: the existing frozen `semantic_algebraic_lift` compiler and
its independent `exact_replay` are digest-pinned and loaded directly; they are
not reimplemented as a new framework. Its truth-free current-style development
census reported semantic frontend upper bound 141/145, finite phase replay
ledger 141/145, selector ledger 145/145, median auxiliary proxy 3/max 67; the
four failures share one phase-variable-escape boundary. This candidate adds
only the target-constrained backend and descriptor-bound certificate. A model
from a lifted source is rejected unless the frozen polynomial replay and fresh
untouched DSL/guard/selector/phase/raw-target replay both pass.

Routing inputs: expression operators, rational coefficients, dimension,
degree/term caps, guard/definedness and the solver-proposed descriptor only.
Case ID, family, truth, expected target, known target count and prior outcomes
are unavailable. This is a cleanroom generated D0; no formal execute, scorer,
truth bundle, development case or CPU0–6 was used.

GO gate: sound activation on at least two independent structures, false accepts
zero, and permutation/equation-scale/reversible-affine-target metamorphics pass.

D0 outcome: `GO_D0`. Sound activation was 5/5 (regular coupled irrational,
singular/nonradical, irrelevant-free positive-dimensional configuration with a
finite target, explicit division, and frozen semantic frontend); false accepts
were 0/6; metamorphics were 3/3. Timeout and nonsquarefree-proposal fail-closed
paths are unit-tested; the complete candidate suite is 10/10. Candidate
mechanism SHA-256 is
`7b98bdfb018d566994291ad75cb2e7f28f62adc960a784ca54d3b68b796586ff`.
No formal scorer or truth-bearing dataset was executed. Next gate is a private
adapter/D1 activation census, not backend parameter tuning.
