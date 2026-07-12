# Experiment Card Template

The canonical machine-readable contract is
[`research/schemas/experiment-card.schema.json`](../../research/schemas/experiment-card.schema.json).
Cards are JSON files in `research/experiments/` and are validated with:

```powershell
python research/validate.py
```

A card must name its requirements and first-failure IDs, cite primary or
official sources with assumptions and break conditions, define permanent
controls and counterexample families, and make every H0 numeric setting an
explicit `hypothesis` hyperparameter. Promotion and kill criteria are arrays of
independently checkable statements; a prose claim such as "looks faster" is not
a gate.

Required sequence: literature/assumption matrix, a source-to-code conformance
trace, reference/adapted/control separation, minimum-success and activation
fixtures, preregistration, counterexample cases, factorial family, paired
same-budget run, ablation, development tuning (at most twice), parameter
freeze, one locked validation, then promote, specialize or causally classify.

A failed performance gate stops promotion but does not by itself reject the
mechanism. Before cleanup, an independent reviewer must distinguish an invalid
run, implementation defect, unexercised mechanism, limited applicability,
budget/parameter limitation, bounded mechanism negative, or an inconclusive
result. Only an independently reproduced bounded mechanism negative authorizes
deletion of its implementation. Other classifications retain a versioned
repair or an explicit reopen gate. The compact result, classification, source
hashes and counterexamples always remain.

The first three canonical cards are:

- `EXP-COMP-001`: compiler semantics and economics;
- `EXP-LOCAL-001`: fixed-start local scaling and derivative routing; and
- `EXP-DISC-001`: full-support sampling and soft topographical ordering.

None names the final solver algorithm.
