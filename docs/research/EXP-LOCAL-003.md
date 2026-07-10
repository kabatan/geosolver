# EXP-LOCAL-003 — semantic-preserving local model scaling

Status: **card-only preregistration**. No generator, mechanism source, input or
result exists at this commit. The machine-readable authority is
[`EXP-LOCAL-003.json`](../../research/experiments/EXP-LOCAL-003.json).

## Semantic boundary

For relation raw value `y_i` and declared semantic scale `s_i`,

```text
z_i = y_i / s_i
```

remains the only internal-termination, canonical-replay and Gold-assessment
residual. `RelationObservation`, plugin ABI, wire and checkpoint bytes are
unchanged.

| Variant | Internal variable coordinates | LM model residual |
|---|---|---|
| `L0-SEMANTIC` | declared origin/scale | `z` |
| `LX-BOUNDS` | finite-bounds midpoint/half-width | `z` |
| `LR-MODEL` | declared origin/scale | `q_i = z_i/a_i` |
| `LXR-BOUNDS-MODEL` | finite-bounds midpoint/half-width | `q_i = z_i/a_i` |

Finite differences observe the unchanged `RelationObservation` values and
first form `J_z`. Only afterward does the model form
`J_q = diag(1/a) J_z`. `q` and `J_q` are used only for merit, the LM step and
predicted-versus-actual step acceptance. LX changes only internal coordinates.
No finite-difference observation, wire value or checkpoint is rewritten. A
nonfinite `q` is `EVAL_NONFINITE` model failure, never semantic convergence or
an endpoint.

## Frozen calibration

Each latent group starts from 64 base physical points generated only from safe
finite public bounds. The generator holds an independent random
`calibration_key`; it is never candidate-visible. For zero-based point `p` and
coordinate `j`,

```text
H = SHA-256(domain || seed32 || calibration_key32 || uint32be(p) || uint32be(j))
n = uint64be(H[0:8]) >> 12
u = (2n + 1) * 2^-53
t = fma(2.0, u, -1.0)
x = fma(halfwidth, t, midpoint)
```

Thus `n` is exactly the top 52 hash bits and the exact dyadic `u` ranges from
`2^-53` through `prevfloat(1)`. Under locked binary64 roundTiesToEven,
`d = upper-lower`; when `d` is finite the generator sets
`halfwidth=d/2, midpoint=lower+halfwidth`, otherwise it sets
`halfwidth=upper/2-lower/2, midpoint=lower/2+upper/2`. Midpoint must be finite
and halfwidth finite and positive. Both calls use the explicit correctly
rounded `Base.fma(Float64,Float64,Float64)` contract; the environment fixture
pins that behavior. C0 rejects any nonfinite or out-of-bounds mapped
coordinate.

The domain is NUL-terminated ASCII
`geotarget.exp-local-003.calibration.counter.v1`; `seed32` is SHA-256 of ASCII
`EXP-LOCAL-003-CALIBRATION-SEED-V1`. The base counter has no Gold, root, start,
outcome, family or representation input. At C0, signed/permuted representations
are deterministic coordinate transforms of the latent base points. Each
case's resulting bytes and checksum are persisted before mechanism source and
are replay authority. Solver and calibrator receive only those points: they
cannot see the `calibration_key`, regenerate points or infer a representation.

A point counts only when its complete observation vector is status-valid and
all `z_i` are finite. With `K` valid vectors, `r_i` is nearest-rank item
`ceil(0.75K)` of sorted `abs(z_i)`. If `K < 8` or any `r_i` is nonfinite or
nonpositive, every `a_i` is one. Otherwise

```text
a_i = clamp(r_i, 0x1.0p-40, 0x1.0p+40)
```

using exact binary64 bit patterns `0x3d70000000000000` and
`0x4270000000000000`. One vector is fixed per case and shared by LR/LXR. The
record preserves point and scale hashes, `K`, every binary64 `r_i/a_i`, and
joint-fallback or component clamp reasons.

## Cases and representation gates

Development has eight families × two latent groups × three primary
representations = 48 cases. The representations are base, deterministic signed
variable/residual permutation, and semantic-equivalent row rescaling. Row
multipliers are exact powers of two; generation rejects overflow, underflow,
subnormal operands or loss of exact `z` equality.

For every variant/start, inverse-mapped canonical and Gold decisions must agree
across the triple, and LR/LXR `a` must permute exactly as declared. This is a
zero-required hard gate. Safety16 adds one orthogonal representation per latent
group with `expected_invariant=false`; it is report-only. Its disagreement
cannot change development statistics, but forbids product connection.

Candidate and assessor data occupy separate immutable trees. Every candidate
case exposes its own independently random `opaque_case_key`, sanitized
compiler/oracle payload, public numeric metadata, persisted case points, starts
and budgets. It exposes neither the generator-only `calibration_key` nor any
field that links a latent group or representation. Only the assessor tree
contains Gold, tolerances, family/group/representation maps and analytic/branch
truth. The solver/calibrator receives only a callable oracle, public numeric
metadata and persisted points, never specification or identity fields. An
unknown-plugin Float64-only C0 path is mandatory.

The mandatory geometry-DSL route is candidate `ProblemSpec` generated by the
Python SDK `ProblemBuilder` plus canonical encoder/validator (never handwritten
JSON) → candidate problem document → `decode_problem_document` → allowlisted
`FrozenPluginRegistry` → `compile_problem` → `evaluate(compiled, C0)` callback
→ local solver → `evaluate_canonical`/`validate_candidate`.
`DirectAnalyticProblem` and hand-built `RelationObservation` substitutes are
forbidden.

## Frozen inference and selection

All variants use 32 paired starts and prefixes 8/16/32. A latent-group recall
effect is the mean paired candidate-minus-L0 binary decision over its three
representations; the overall effect equally weights 16 groups. Families and
positive-family count are descriptive. At prefix 32, a selected recall-path
candidate counts only families with recall delta strictly `> 0`; a selected
efficiency-only candidate counts only families with recall delta `>= -0.02`
and ERT reduction strictly `> 0`. At least three families must count. These two
positivity tests are strict even though all other frozen threshold equalities
pass.

Every primary family is critical: `SCALE-LADDER`, `CURVED-CHAIN`,
`NEAR-RANK-DEFICIENT`, `REDUNDANT-OVERDETERMINED`,
`TANGENT-CIRCLE-LINE`, `MULTIROOT-WARPED`, `STRICT-GUARD-BOUNDARY`, and
`OPAQUE-TRANSCENDENTAL-C0`. No one of these eight may have descriptive recall
delta below -0.02 at a mandatory prefix.

Each start has hard caps of 250 local iterations and 2,000 local evaluations.
C0 records the `LocalSolveOptions` source hash, both integers, and exact
binary64 hexadecimal values of residual tolerance, step tolerance,
finite-difference step, initial damping, damping increase and damping decrease.
Every variant and representation receives identical values and the candidate
mechanism cannot alter them. The 64 LR/LXR calibration observations are
separate charged work and do not consume a start's 2,000-evaluation cap.

For case `c`, let `L_c = compiled.logical_evaluation_cost > 0`. A Gold-valid
start is charged the sum of reported `evaluation_cost` for every base, finite-
difference, trial, and rejected-step compiled observation, plus one canonical
replay. A non-Gold-valid start replaces its local sum by `2000*L_c`, then adds
the canonical replay cost. At each prefix 8/16/32, LR/LXR additionally charge
the reported costs of exactly 64 calibration observations per case; invalid
observations still count and prefixes never amortize one another. L0/LX run no
calibration. ERT pools this numerator and divides by Gold-valid starts, becoming
`+Inf` when none succeeds.

Factorization, compilation, allocations, input generation, and assessor-only
Gold matching receive no invented oracle-work conversion. They are counted
exactly once in process/end-to-end CPU and host-valid wall metrics. Common C1
point materialization is therefore reported but never double charged.

For reduction, let `B` be L0 ERT and `C` candidate ERT; finite `B` is strictly
positive. The frozen extended-real result is `1-C/B` for finite/finite, `1` for
`B=+Inf` and finite `C`, `-Inf` for finite `B` and `C=+Inf`, and conservatively
`0` when both are `+Inf`. Candidate/L0 ratio is `C/B` for finite/finite, `0` for
`B=+Inf` and finite `C`, and `+Inf` whenever `C=+Inf`. JSON stores infinities
only as tagged strings `"+Inf"` and `"-Inf"`, never nonstandard numeric tokens.

Exactly 100,000 paired family-stratified bootstrap replicates resample latent
groups with replacement inside each family. SHA-256 counter/rejection mapping,
domain/seed, stage byte and index bytes are fixed in the card and persisted.
Nearest-rank items 5,000 and 95,000 are the one-sided 95% lower/upper bounds;
all threshold comparisons are inclusive except the two explicitly strict
family-positivity tests. Recall thresholds are absolute probability-point
differences, while ERT thresholds are relative fractions.

Family ordinals are the eight critical IDs in the order listed above. Each
stage persists one byte stream: ASCII `GTLOCAL3BOOT1`, NUL, stage byte `D`/`L`,
big-endian UInt32 values `(100000, 8, G)`, then UInt8 indexes in
replicate-major, family-major, draw-minor order, where `G=2` for development
and `G=4` for locked validation. SHA-256 covers header and payload. The same
indexes pair every candidate, metric, and prefix.

If multiple candidates pass, recall-path candidates outrank efficiency-only
candidates. Recall-path ordering maximizes lower recall bound then minimizes
ERT; efficiency ordering maximizes lower ERT-reduction bound then recall.
Exact ties prefer LX, then LR, then LXR. The one selected candidate alone enters
locked validation against L0, with no reselection.

## One-shot execution chain

1. `C-1`: this final card/documentation only.
2. `C0`: generator, materializer, assessor, schemas, environment and numeric
   JSON-domain fixture; no mechanism.
3. `C1`: exactly one candidate/Gold development materialization and hash seal.
4. `C2`: mechanism, tests and exact L0 default-equivalence evidence.
5. `C3`: exactly one candidate-only formal development execution; hash and
   seal its complete raw output, close that process, then open the assessor tree
   in a separate process, verify the seal and assess the frozen decision.

A C1–C3 protocol/infrastructure failure is terminal and authorizes no retry.
Only a valid passing C3 can materialize 96 fresh locked cases (eight families ×
four new latent groups × three representations). Locked validation repeats the
physical candidate/assessor split and one-shot seal/open sequence, running only
the frozen champion against L0. Replacement is allowed only for pre-outcome
input invalidity. Once any locked outcome is visible, failure stands: no
replacement, retry, reselection or threshold change.
