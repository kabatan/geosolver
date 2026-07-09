# Failure Taxonomy

The Miss Analyzer reports the first failed checkpoint in this chain:

`truth -> sample -> capture -> local solve -> canonical residual -> domain -> guard -> branch -> archive -> scheduler -> high precision -> configuration certificate -> target identity proof -> output deduplication`

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

No case-specific repair is implemented before a minimal reproduction, a
parameterized failure family, a counterexample family and a counterfactual trace
identify the responsible checkpoint.

