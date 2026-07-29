# Compiled geometry kernel qualification

The compiled numeric kernel is a candidate implementation, not a new solver
algorithm. It must remain disabled for an entire problem until this gate passes.
The frozen reference evaluator is the oracle; frozen champion decisions are not
redefined by this harness.

## Corpus and probes

Qualification consumes exactly the 145 frozen V15 `problem.json` files. For
each problem it deterministically derives probes from the problem SHA-256:

- seeded random points inside finite source bounds (unbounded coordinates use
  the harness-only `[-2, 2]` probe envelope);
- each lower and upper boundary and the adjacent interior binary64 value;
- zero, coincident-coordinate, smallest-positive-normal, negative-smallest-
  normal, and midpoint degeneracies.

The probe envelope is test input generation only. It is never supplied to the
solver and cannot add or infer a source bound.

The 145 problems are a sample, not an allowlist. The adapter must expose a
compiler manifest with `case_specific_routing=false` and declare that support
is decided only from the AST primitive and inferred-type sets. Each prepared
case emits its sorted primitive/type sets plus negative read attestations for
problem ID, corpus membership, truth, and answer count. The harness replaces
every corpus ID with a new synthetic ID while preserving its V15 AST and
requires the same support trace and compiled/fallback route. Any corpus- or
case-specific dispatch fails qualification. The manifest fixes the support key
to AST opcodes, resolved operand/result types, selector kinds, and the semantic
ABI version; problem/source hashes and corpus shape are forbidden. The harness
also parses the isolated support-
decision function and rejects static reads of problem/case ID, source/problem
hash, corpus membership/shape, truth, or answer count.
Fallback decisions must retain the actual non-empty opcode and resolved-type
sets, selector kinds, and semantic ABI in their trace. A generic empty
"unsupported" signature cannot satisfy the gate because it would hide
case-specific routing among rejected programs.

Three additional corpus-independent V15 compositions combine `Point`,
`Distance`, `Line`, `Area`, `Angle`, and `PointOnCircle` with previously unseen
`near`, `far`, and `exclude` intersection arrangements. Each must enter the
compiled route and produce zero differential on generated probes at every core
count. A safe fallback is necessary product behavior, but does not satisfy this
generality qualification fixture.

## Equality contract

The production `production_strict` gate targets the SymPy/libmp-compatible
RefNum backend. Every value and residual uses byte-for-byte IEEE-754 equality,
including the sign of zero, NaN payload, and non-finite classification.

A separate `experimental_numeric_equivalence` report may study a native/libm
backend. Only values and residuals explicitly identified by both evaluators as
transcendental may differ by at most 2 ULP, and their branch tokens must be
identical. Signed zero and non-finite values remain bitwise. This shadow mode
always reports `production_admissible=false` and can never produce a product
qualification pass.

The following decision-bearing fields always require exact equality:

- residual vector, including element order and binary64 bits;
- every guard outcome;
- ordered guard violation strings;
- hard-feasibility outcome;
- ordered hard-failure tags and bitwise minimum margin;
- every threshold decision;
- canonical candidate record, including IDs, ranks, endpoints, counters, and
  rejection/acceptance metadata;
- exception type, normalized exception stage, evaluation status, and ordered
  non-finite classifications.

## Fallback and core gates

Compilation is all-or-nothing per problem. An unsupported problem must name a
non-empty fallback reason and its candidate route must reproduce the reference
observation for every probe. Qualification must exercise at least one fallback
case; silently mixing compiled and reference nodes within one problem is not a
qualifying fallback.

Every probe is repeated with requested core counts `1, 2, 4, 8, 15`. Candidate
observations must satisfy the reference contract at every count. Across core
counts, every candidate value must be bitwise identical to the one-core
candidate value, including values produced by transcendental operations; the
2-ULP allowance applies only between candidate and reference implementations.

The production default generates at least 64 seeded random probes per problem.
In addition, the adapter or `--replay-trace` input must supply points and
candidate traces actually visited by the frozen optimizer. Qualification fails
when no optimizer replay probe is exercised. JSON/JSONL replay rows use
`{"case_id": ..., "trace_id": ..., "point": [...]}`; candidate observations
must preserve frozen endpoint SHA-256, `record_id`, and `admission_role` in the
candidate record when the trace reaches candidate admission.

## Adapter and report

An adapter implements `KernelQualificationAdapter.prepare(problem, cores=...)`
and returns a `PreparedKernelCase` defined in
`geotarget.kernel_qualification`. The prepared case exposes source bounds,
whole-problem support/fallback metadata, and `reference(point)` plus
`candidate(point)` evaluators.

Run the standalone gate outside the product solve process:

```bash
uv run python -m geotarget.kernel_qualification \
  --corpus /path/to/frozen-145/cases \
  --adapter package.module:create_adapter \
  --replay-trace /path/to/optimizer-points.jsonl \
  --report /path/to/kernel-qualification.json
```

The command exits `0` only when every gate passes and writes the report
atomically. A non-passing report must leave the product in whole-problem
reference fallback mode.
