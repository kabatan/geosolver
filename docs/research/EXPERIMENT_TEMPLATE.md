# Experiment Card Template

```yaml
id: EXP-YYYY-NNN
status: preregistered | running | completed | promoted | rejected
hypothesis: ""
failure_ids: []
requirements: []
literature:
  - source: ""
    assumptions: ""
    break_conditions: ""
controls: []
candidate: ""
applicability_predicate: ""
success_families: []
counterexample_families: []
fixed_parameters: {}
tuning_round_limit: 2
seeds: []
budgets_seconds: [60, 180, 420]
primary_metric: "P_full_validated"
non_regression_metrics: []
promotion_gate: ""
kill_gate: ""
implementation_commit: ""
manifest_path: ""
result_path: ""
decision: ""
```

Required sequence: literature/assumption matrix, preregistration, minimum
success and counterexample cases, factorial family, paired same-budget run,
ablation, development tuning (at most twice), parameter freeze, one locked
validation, then promote/specialize/reject. Rejected code is deleted; its card,
compact results, checksums and counterexamples remain.

