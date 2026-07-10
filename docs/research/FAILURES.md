# Failure Taxonomy

The Miss Analyzer reports the first failed checkpoint in this chain:

`truth -> reference/plugin semantics -> compilation -> sample -> capture -> local solve -> canonical residual -> domain -> guard -> branch -> archive -> scheduler -> high precision -> configuration certificate -> target identity proof -> output deduplication`

| ID | Failure |
|---|---|
| F0 | Gold truth or expected-answer error |
| F1 | Reference/compiled semantic mismatch |
| F2 | Domain-invalid evaluation or unsafe step |
| F3 | Variable/residual scaling failure |
| F4 | Coverage/sample did not enter a capture region |
| F5 | Local solver failed inside a capture region |
| F6 | Convergence to a nonzero stationary point |
| F7 | Branch/chart selection failure |
| F8 | Guard/boundary classification failure |
| F9 | Singular root, tangent system or feasible manifold failure |
| F10 | Archive lost or irreversibly merged a needed witness |
| F11 | Fair scheduler starvation or duplicate work |
| F12 | High-precision refinement failure |
| F13 | Configuration validity certificate failure |
| F14 | Target algebraic identity proof failure |
| F15 | Final target deduplication/output failure |
| F16 | Adaptive-unbounded shell coverage failure |
| F17 | Seed, thread, precision or machine nondeterminism |
| F18 | Compiler, screening or coordination overhead erases the claimed same-budget gain |

No case-specific repair is implemented before a minimal reproduction, a
parameterized failure family, a counterexample family and a counterfactual trace
identify the responsible checkpoint.

## Implemented diagnostic coverage

[Miss Analyzer v0.2](MISS_ANALYZER.md) implements a strict research-side
schema/API/CLI. It selects by checkpoint order in the chain above rather than by
numeric F-ID order. A classification requires causal, target-relevant evidence;
missing or unassociated telemetry yields `unknown`.

| ID | v0.2 evidence accepted |
|---|---|
| F0 | Independent truth-audit fact only |
| F1 | Reference/compiled differential fact only |
| F2 | Uniquely target-associated canonical domain failure, or typed counterfactual fact |
| F3 | Reference differential or counterfactual scaling fact only |
| F4 | Instrumented capture or counterfactual no-entry fact only |
| F5 | Target-associated near-feasible failed local status, or capture-backed local fact |
| F6 | Capture-backed stationary-point/counterfactual fact only |
| F7 | Run branch mismatch, target-associated canonical branch failure, or counterfactual fact |
| F8 | Run guard/boundary mismatch, target-associated canonical guard failure, or counterfactual fact |
| F9 | Target-associated singular/unresolved target-image diagnostic, or counterfactual fact |
| F10 | Archive-audit fact, or an automatic canonical-valid verified trace witness uniquely associated with a target missing from final validated output |
| F11 | Scheduler-audit fact only |
| F12 | Target-associated refinement/resource diagnostic, or counterfactual fact |
| F13 | Run configuration invalidity or target-associated canonical semantic/certificate failure |
| F14 | Validated-complete exact shortfall, exact answer without identity proof, or typed validation fact |
| F15 | False/ambiguous output, false completeness claim, or output-audit fact |
| F16 | Scheduler/instrumented adaptive-shell fact only |
| F17 | Determinism-audit fact only |
| F18 | Same-budget performance-comparison fact only |

Finite absence is never treated as F4, F11 or F16. See the v0.2 document for
the paths intentionally left unclassified.
