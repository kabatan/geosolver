# Miss Analyzer v0.2

The Miss Analyzer is a research-side diagnostic tool. It does not change the
solver, geometry ABI, public presets or answer-assurance semantics. Given one
typed `CaseInput`, its `RunInput`, and the exact `RunEvaluation` recomputed by
the benchmark harness, it returns the earliest **evidenced** failed checkpoint
from [the common taxonomy](FAILURES.md).

The report is diagnostic, not a completeness certificate. In particular, the
absence of an event never proves that a sample missed a capture region, that a
scheduler was fair, or that the finite output is complete.

## Inputs and output

The Python API is `research.harness.miss_analyzer.analyze_miss`. It requires the
typed values `CaseInput`, `RunInput`, and `RunEvaluation`; it rejects a supplied
evaluation unless it is exactly equal to `evaluate_run(case, run)`.

Three optional evidence inputs are accepted:

1. `geotarget.evidence-log/v1`, emitted by the Julia solve path;
2. `geotarget.checkpoint/v1`, whose observation events use the lossless typed
   real representation;
3. `geotarget.miss-diagnostics/v1`, containing separately audited causal facts.

The first two inputs are parsed structurally and current `Observation`
diagnostics are mapped by typed status values. Version 0.2 also performs one
strict automatic archive audit: if a canonical-valid `verified` observation
uniquely associates with a still-missing validated Gold target, the same trace
proves that the witness passed verification before disappearing from the final
answer set, so the run is classified as F10. Unverified observations, ambiguous
target associations and exact-only shortfalls do not trigger that audit. A raw
checkpoint should first be accepted by the Core checkpoint decoder when
cryptographic content-hash authentication matters; the research parser does
not replace that decoder.

The sidecar diagnostic schema deliberately separates a fact from its source.
For example, `gold_truth_invalid` is accepted only from an
`independent_truth_audit`; `capture_region_not_entered` requires instrumented
capture or counterfactual replay; archive, scheduler, determinism and overhead
facts require their corresponding audits. Every fact has a subject, an evidence
reference and an explicit `causal` flag. Noncausal observations are retained as
unknown rather than promoted to a diagnosis.

The output is canonical, deterministic `geotarget.miss-report/v1` JSON with one
of three outcomes:

- `no_failure`: benchmark Gold is fully covered at the required assurance level
  with no safety violation;
- `classified`: `failure_id` and `checkpoint` identify the earliest evidenced
  failure, and `evidence` contains the typed facts used for that decision;
- `unknown`: no causal fact establishes a failure checkpoint, with typed reason
  codes explaining what is missing.

Schemas live at:

- `research/schemas/miss-diagnostics.schema.json`
- `research/schemas/miss-report.schema.json`

## CLI

The CLI consumes individual strict `CaseInput` and `RunInput` JSON documents;
it recomputes `RunEvaluation` and never accepts a serialized metric summary as
truth.

```powershell
python -m research.harness.miss_analyzer `
  --case case.json `
  --run run.json `
  --evidence-log evidence.json `
  --checkpoint checkpoint.json `
  --diagnostics miss-diagnostics.json `
  --output miss-report.json
```

All three evidence switches are optional. Omitting them for an incomplete run
normally produces `unknown`, not F4. The command must be run only on a
development-readable or formally burned benchmark partition; it never opens a
locked or blind partition by itself.

## Conservative trace association

An observation diagnostic is causal for a missing target only when its target
enclosure associates with exactly one relevant Gold target. Certified-interval
cases require containment inside that Gold interval (mere overlap is too weak
for non-certified trace data); declared-tolerance cases reuse the declared
midpoint/width rule. Diagnostics with no target, an ambiguous target, or a target
already covered at the required level are not used to classify the miss.

Current automatic mappings include:

| Typed observation fact | Failure |
|---|---|
| `CANDIDATE_DOMAIN_FAILED` | F2 |
| failed local status after a uniquely associated near-feasible observation | F5 |
| guard separation/validity failures | F8 |
| branch key/selector/validity failures | F7 |
| singular, unresolved or insufficient target-image linearization | F9 |
| target-image deadline/cancellation/oracle budget or required refinement | F12 |
| canonical relation truth/residual, bounds, replay or target-consistency failure | F13 |

Run evaluation independently identifies false guard/boundary/branch outputs,
configuration-certificate failures, target-identity shortfalls, false outputs
and false completeness claims. The verified-trace/final-output comparison above
is the only automatic F10 route. A wrong Gold table (F0), no-capture statement
(F4), other archive claims, scheduler defect (F11) and same-budget overhead
(F18) require dedicated typed audit facts; they are not guessed from case
names, primitive names, elapsed time, or absent events.

## Known unclassified paths

These remain `unknown` until an appropriate instrument or counterfactual audit
is supplied:

- a domain/evaluation/local failure that cannot be associated with a missing
  target;
- a budget-exhausted, deadline, pause, callback or protocol status without a
  causal target-level diagnostic;
- zero observed capture events in a finite trace;
- finite-lane counts offered as proof of asymptotic scheduler fairness or shell
  coverage;
- a missing final answer when the trace has no uniquely target-associated
  canonical-valid `verified` observation proving that the archive once held it;
- target-image capability absence that does not itself identify singularity,
  refinement failure or semantic invalidity;
- compilation, scaling and nondeterminism claims without a differential,
  counterfactual or replay audit.

Extending this list requires a parameterized counterexample, typed evidence and
a test showing that the new signal does not turn missing telemetry into success
or a more specific failure.
