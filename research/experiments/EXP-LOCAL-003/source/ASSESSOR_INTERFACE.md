# EXP-LOCAL-003 C0 assessor interface

This directory freezes the assessor/statistics side of card SHA-256
`0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c`.
It contains no problem generator and no candidate solver mechanism.

The C2 runner writes a sealed document accepted by
`candidate-output.schema.json`. A physically separate assessor process receives
that document, the C1 Gold document accepted by
`assessor-truth.schema.json`, the persisted bootstrap-index bytes, and the
independently frozen C2/C3 source/artifact allowlist accepted by
`candidate-execution-lock.schema.json`. Its only entry point is:

```python
assess(raw_document, assessor_truth, bootstrap_bytes, execution_lock) -> json_safe_document
```

`assessor.py` is authoritative for cross-field rules that JSON Schema cannot
express. In particular it checks exact keys, the stage-specific variant set,
64/96-case topology, unique opaque joins, family/group/representation
allocation, vector lengths, permutations, calibration hashes, and the physical
candidate/assessor access boundary. The JSON schemas are the structural/type
boundary and reject unknown properties.

## Physical split

Candidate raw cases carry only:

- a random 64-hex `opaque_case_key`;
- exact problem, calibration-point and ordered-start digests recorded by the
  independent runner;
- `variable_count`, `residual_count`, and positive
  `logical_evaluation_cost` public execution metadata;
- L0/LX/LR/LXR result records (or L0 plus the frozen candidate for locked
  validation).

They never carry family, latent-group, representation, expected-invariant,
Gold, tolerance, or assessor fields. The execution lock freezes sorted
`{path, sha256}` source and candidate-artifact allowlists plus the Julia
runner path/hash. Its `stage_input_anchor_sha256` and
`stage_input_anchor_commit` bind development or locked execution to that
stage's exact pre-outcome input anchor. The runner's complete `loaded_sources`
and `opened_artifacts` records must equal those lists and are cross-checked by
the immutable C0 observer. Assessor, Gold, truth,
generator, materializer and private identity tokens are forbidden even in a
filename such as `assessor.py`; every artifact remains below the `candidate/`
root. These records come from the C3 process boundary, never candidate
self-attestation. The candidate process never receives this module, the Gold
vault, generator/materializer source, or repository history.

Assessor truth owns the family ordinal, latent-group index/key,
representation, Gold configurations/targets/tolerances, and expected
calibration audit. Candidate and truth join only on `opaque_case_key`; their
input, problem, point, start and local-options digests, variable/residual
counts, logical cost, stage, and complete key sets must agree.

There are four truth rows per family/group: three hard primary
representations and one `orthogonal-safety` row with
`expected_invariant=false`. Thus development has 8×2×4 = 64 raw/Gold cases,
of which only 48 enter efficacy statistics. Locked validation contains four
fresh groups and only the three primary representations: 8×4×3 = 96 cases.
Development Safety16 disagreements block final product connection, but neither
select a champion nor block preregistered locked materialization. A later
closure must join the bound development Safety16 result to the locked result;
neither stage-local assessment can authorize product connection alone.

## Raw result grammar

Every case has one result for each stage-required variant. Every result binds
the exact frozen `LocalSolveOptions` digest and has exactly 32 attempts with
unique `start_index` 0…31. An attempt records:

- `iterations` (kept assessable above 250 so it becomes a hard budget event);
- `accepted`;
- one nonnegative `evaluation_cost` per compiled local observation (kept
  assessable above 2000 observations for the same reason);
- exactly one canonical replay with its independent validity, physical
  configuration, target, branch label, and nonnegative replay cost.

Configurations have `variable_count` binary64 values. Calibration vectors have
`residual_count` values; this distinction is required for overdetermined
systems. Every binary64 value uses canonical Python `float.hex()` form. Julia
must emit the identical form (13 hexadecimal fraction digits for nonzero
values; canonical zero is `0x0.0p+0` or `-0x0.0p+0`).

L0 and LX have `calibration=null`. LR and LXR have exactly 64 observation
costs, the complete-vector valid count, nearest-rank vector, model-scale vector,
canonical scale hash, joint fallback, per-row lower/upper clamp flags, and
nonfinite-q audit counts. The scale hash binds:

```
ASCII "GTLOCAL3AVEC1" || NUL || uint32be(residual_count)
    || residual_count IEEE-754 binary64 big-endian words
```

`semantic_or_wire_drift_count` and `identity_access_count` are sealed audit
events. C2/C3 must produce them from independent instrumentation; they are not
permission for candidate self-attestation.

Persisted assessment JSON is encoded by the repository
`geotarget.canonical.canonical_bytes` RFC 8785 JCS implementation after
extended-real tagging. The strict loader deliberately accepts either an integer
or floating JSON token for a finite numeric field; lexical `1` versus `1.0`
therefore cannot change assessment truth.

## Gold and correctness

Gold matching ignores solver convergence status. A start is Gold-valid only if
the candidate accepted it, unchanged canonical replay is valid, and its
configuration infinity error, target absolute error, and optional branch label
match at least one independent Gold solution. An accepted non-Gold or
canonical-invalid endpoint is a hard false-candidate event.

For every variant/start, `(accepted, canonical-valid, Gold-valid)` must agree
across the three primary representations. LR/LXR scales must additionally equal
the truth audit and the assessor-only residual permutation of the base scale.
These are hard failures. A hard failure in *any* development variant kills the
whole development stage; a safe candidate cannot hide another candidate's
violation. The same decision comparison against the orthogonal row is
report-only development Safety16. There is no unregistered locked Safety32.

## Work and statistics

At prefix `p` in 8, 16, 32, one primary case contributes:

- Gold-valid start: the sum of all actual local observation costs plus its
  canonical replay cost;
- other start: `2000 * logical_evaluation_cost` plus its replay cost;
- LR/LXR: one complete 64-observation calibration cost at each prefix;
- L0/LX: zero calibration cost.

CPU, wall time, compilation, factorization, allocation, input materialization,
and Gold matching never enter oracle-work ERT. ERT pools work and successes
over selected latent groups and is `+Inf` for zero successes. Extended values
are JSON strings `"+Inf"` and `"-Inf"`; NaN and nonstandard JSON numeric
literals are forbidden.

The paired recall effect is computed within each latent group over its three
primary representations and starts. Overall inference equally weights 16
development (or 32 locked) groups. Each of 100000 bootstrap replicates resamples
G groups with replacement inside each of the eight families and uses the same
indexes for every variant, prefix, recall, and ERT statistic. Bounds are sorted
one-indexed items 5000 and 95000. Gate comparisons are inclusive, except
family recall `>0` and family ERT reduction `>0` in the path-specific breadth
rule.

`bootstrap_index_bytes(stage)` creates the exact C0 table;
`bootstrap_sha256(stage)` binds its complete 27-byte header plus UInt8 payload.
After C1, the persisted bytes and digest—not regeneration—are authority.

Development selection is deterministic. A passing recall-path candidate always
outranks an efficiency-only candidate. Recall candidates sort by decreasing
recall lower bound, increasing candidate ERT, then LX/LR/LXR simplicity.
Efficiency candidates sort by decreasing ERT-reduction lower bound, decreasing
recall effect, then the same simplicity order. Locked truth freezes one
candidate and its development path and binds the development assessment and
decision-record hashes; locked assessment never reselects. Assessment output
binds the candidate input/output, truth, bootstrap, local-options and
execution-lock digests and reports absolute L0/candidate Gold recall and
calibration fallback counts as well as deltas and ERT.
