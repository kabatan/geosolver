# Core-owner patch proposal

## Required integration

Add one source-dimension fast path before start generation:

```text
if unchanged_source.variables.names has length 0:
    require endpoint == []
    result = zero_dimensional_authority.run_zero_dimensional_authority(
        unchanged_source_bytes,
        frozen_source_digest,
        [],
        backend=unchanged_source_numeric_replay_backend,
    )
    require result.status == EXACT_SYMBOLIC_TARGET_READY
    require result.exact_authority_kind ==
            SOURCE_EXACT_SYMBOLIC_MINPOLY_ISOLATOR
    require result.numeric_pslq_descriptor_used == false
    require source certificates and numeric replay parity
    convert only result.exact_target_descriptor into the finalizer schema
    atomically finalize that one exact target
else:
    run champion_v1 exactly as before
```

Do not read source `id`, truth, target count, family, file name, or prior
outcome. Do not add bounds or reinterpret the problem.

## Critical authority boundary

The exact descriptor must come only from `candidate.py`'s exact source AST
evaluation. In particular:

- never copy `target_authority`, PSLQ relation, minpoly, isolator, or root index
  from the numerical replay artifact;
- never treat 768/1024 agreement as algebraicity proof;
- reject unsupported source operations rather than falling back to numerical
  recognition;
- require exact truth of every source constraint and guard;
- retain Float64 and 512/768/1024 replay only as source-implementation parity.

`bridge.py` is now explicitly diagnostic-only. It may be used to reproduce
the old replay artifact, but must not be configured as the final exact HP
bridge. The earlier numeric direct-dispatcher smoke is historical diagnosis,
not promotion evidence.

## Why the bypass belongs above multistart

There is one configuration, `[]`. Spending the 146-second search budget cannot
discover another configuration and was the direct cause of the regression.
The bypass is both faster and semantically simpler than relaxing nonempty
contracts throughout adaptive HP.

## Finalizer conversion

The candidate descriptor provides:

- `minimal_polynomial_high_to_low`;
- `exact_relation_low_to_high`;
- primitive/square-free/irreducible flags;
- `selected_real_root_index`;
- an exact open rational isolating interval;
- an exact value-expression hash;
- explicit `numeric_pslq_used: false`.

Map these fields to the existing exact target record. Do not synthesize
`proposal_relation_*`, `confirmation_relation_*`, or numeric residual claims;
those names would incorrectly imply PSLQ authority. If the finalizer currently
requires them, add a separate source-exact descriptor variant rather than
forging numeric evidence.

## Required promotion checks

1. Run the 25 unit tests.
2. Re-run `run_light_smoke.py`; require 4/4 end-to-end positives, 17/17 safe
   non-authority outcomes, exact extreme-lexeme and nested-Boolean guard
   certificate passes, and false/extra 0.
3. Re-run `run_stored_exact_audit.py`; require both exact polynomials and
   `numeric_pslq_descriptor_used: false`.
4. Verify the candidate and evidence digests against
   `IMPLEMENTATION_DIGESTS.json`.
5. Run a paired development145 ablation with only this bypass changed.
6. Require the `OMC009(C)` exact-set restoration and no descriptor/route change
   for any positive-dimensional source.
7. Keep generated `pi`, false tiny equation, unsupported AST, and malicious
   numerical-descriptor tests as hard gates.

## Files to freeze in the experiment plan

- candidate module and digest;
- generated tests and evidence digests;
- source-exact authority kind;
- `zero_dimensional_search_bypass: true`;
- `numeric_pslq_zero_dimensional_authority: false`;
- `source_ast_exact_target_required: true`;
- `exact_source_constraints_and_guards_required: true`;
- `positive_dimensional_path_unchanged: true`;
- `case_family_truth_target_count_routing: false`.

No shared file is modified by this proposal; the common worker owner should
perform the small integration after independent validation.
