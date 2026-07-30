# Decision: generated D0 passes; hold before source connection

Decision: **`D0_GENERATED_GATE_PASS / HOLD_FOR_SOURCE_SEAM_AUDIT`**.

The new state is an accumulated local polyhedron of Boolean-bracketed
semantic-invalid cuts.  It is not a filter/restoration retune and passed the
predeclared mechanism gate:

- safe-root gain/loss `+60/-0` over three positive families;
- semantic-invalid evaluations `5880 -> 1878` at equal 100-callback caps
  (`68.061%` reduction);
- false descriptors `0/120` across infeasible, strict-boundary, isolated
  invalid, nonconvex, nonfinite, and opaque negative/near-miss cases;
- metamorphic failures `0/12`;
- positive callback mismatches `0/60`;
- ordinary/side routing `75%/25%`;
- generated unit tests `11/11`.

Freeze this D0 as mechanism evidence.  Do not run a real case, formal worker,
scorer, truth-bearing artifact, validation, or sealed input from this branch.
The next admissible action is a read-only source seam audit proving that the
current candidate-private worker can identify a source-valid *accepted* point
and its rejected semantic-invalid trials.  An evaluated-point stream without
accepted/trial attribution is insufficient and must fail closed.

The fixed-cap D0 deliberately instantiates the diagnosed no-information
ordinary churn.  After a candidate root is independently replayed, remaining
calls are source-valid accounting observations so paired arms use identical
caps.  Therefore this is causal generated evidence, not a claim about real
recall or production speed.
