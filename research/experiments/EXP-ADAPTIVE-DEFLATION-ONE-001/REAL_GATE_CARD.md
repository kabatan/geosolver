# ADAPTIVE_DEFLATION_ONE real applicability gate

Status: scanner frozen for Root-owned degree1 panel85; fresh-refiner connector added, real run pending.

The gate does not run the proposal and does not inspect a scored outcome.  Its
strict input record contains only an untouched source path+digest, a bare
Float64 endpoint, and the baseline numerical-refinement summary.  Extra fields
(including case/family/truth/score/outcome) reject the record before access.

Eligibility is the conjunction of:

- source solve system is square with exactly two variables and two residuals;
- source residuals expand through the existing exact geometry context and
  admit exact SymPy Jacobian and Hessian without nonsmooth/branch nodes;
- the unchanged source evaluator says the endpoint is semantic-safe with
  residual infinity norm at most `1e-8`;
- baseline refinement mechanically missed its contract
  (`numeric_v3_ready=false`, target stability not ready, and frozen failure
  status `TARGET_STABILITY_FAILED` or `HIGH_PRECISION_REFINEMENT_FAILED`);
- after source-coordinate and residual-row normalization, the 2x2 Jacobian has
  one retained direction and singular ratio below the candidate's frozen
  `1e-6` window, while the left-null projected second directional derivative
  is nonzero above arithmetic uncertainty.

The internal structural signature ignores names and numeric constants and is
canonical over the two variable permutations.  It uses only exact residual
operator histograms and Jacobian/Hessian zero patterns.  No signature value is
emitted.  Activation requires at least four eligible endpoints and at least
two distinct signatures.

Output contains aggregate stage/rejection counts and `signature_count` only;
it contains no path, source hash, endpoint, signature, case identity, family,
truth, score, or outcome.  A passing gate only authorizes a later proposal-only
connector with at least 75% baseline quota and unchanged canonical authority.
It does not authorize direct singular-root promotion.

Root invocation (CPU14, one native thread):

```sh
taskset -c 14 env OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 \
  OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  PYTHONHASHSEED=0 /home/kabatan/work/solver/.venv/bin/python \
  real_gate_scanner.py --input "$ROOT_PANEL85_MANIFEST" \
  --output "$OUTSIDE_REPOSITORY_AGGREGATE"
```

The manifest schema is
`geotarget.adaptive-deflation-one-real-gate-input/v1`; each record must have
exactly `source_path`, `source_sha256`, `endpoint`, and
`refinement_contract`.  The refinement object permits only `variant`,
`status`, `numeric_v3_ready`, and `target_stability_ready`; all four are
required and no other field is accepted.  Root must not include scored
outcomes or identity metadata.

`run_root_panel.py` is the disposable Root-only connector for the existing
degree-one endpoint panel.  It prefilters to square 2x2 sources, runs the
frozen REAL61 refiner in a fresh process, and supplies only its mechanical
ready/miss status to this scanner.  Refiner failures and timeouts fail closed
as misses and still must pass the untouched semantic endpoint and normalized
corank-one tests.  The connector publishes aggregate counts only and never
enables a proposal or authority.
