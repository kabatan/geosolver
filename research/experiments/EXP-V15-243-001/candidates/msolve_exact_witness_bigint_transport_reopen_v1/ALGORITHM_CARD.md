# MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1

## Current production-connector decision

`PRODUCTION_CONNECTOR_D0_PASS__HOLD_SELECTED9_PILOT`.

The serialization reopen remains valid, and the selected runner now binds a
complete ordinary HP proposal rather than a degree-one projection. Only
saved/generated D0 was run. The selected-nine pilot and every heavy
msolve/Julia execution remain benchmark-owner-only under the global lock.

## Historical transport decision

`REOPEN_GATE_SATISFIED`; promote the mechanism only to bounded development
integration. The old msolve/QQBar family is no longer blocked by the recorded
serialization defect. This result does not establish corpus recall or
target-image completeness.

## Hypothesis and minimal repair

The frozen prior D0 reached the QQBar worker, but JSON3 inferred an integer
coefficient outside its native range through a floating representation. The
downstream exact parser then correctly rejected the scientific spelling
`-1.2592661468659425e19`.

The repair is schema-directed and case-independent:

- values in declared exact ZZ coefficient arrays are emitted as canonical
  decimal strings;
- DAG indices, counts, booleans, and other structural values keep their old
  JSON types;
- float values, malformed decimal spellings, empty exact arrays, and large
  integers outside a declared exact field fail closed;
- the adapter decodes its own output and requires canonical mathematical-job
  equality before Julia is started.

No source compiler, RUR algebra, descriptor construction, QQBar operation,
deadline, or acceptance predicate was changed.

## D0 evidence

The serialization D0 passed 13/13 checks on CPU14. It included 256 deterministic
random integers up to 4,077 bits, fixed values around the signed-64-bit boundary,
and a 4,096-bit coefficient. Python encode/decode and Julia JSON3-to-BigInt
round-trips were exact. Scientific notation, floats, booleans in coefficient
arrays, signed/leading-zero spellings, whitespace, empty exact arrays, and an
unclassified 200-bit structural integer were rejected.

The one authorized frozen old-job replay then passed without changing its
8.25-second inner deadline. It transported 29 exact integers (maximum 55 decimal
digits), preserved the mathematical job hash under inverse decoding, and
completed the FLINT/Nemo replay. The augmented job checked 26 relation roots,
21 guard roots, 225 DAG nodes, the raw source answer, and the target descriptor link.
The Nemo stage completed in about 1.94 seconds and the complete worker in about
3.48 seconds.

## Authority boundary

The transport sidecar sets exact-replay authority only because complete QQBar
source replay succeeded. The emitted witness remains development-only:
collector authority is false, truth and post-processing are unused, and no
target-image completeness claim is permitted.

No formal scorer, 98-case corpus, validation set, sealed set, or offline truth
was read. The only corpus artifact replayed was the explicitly frozen old
development job used to establish the causal reopen condition.

## Anonymous static applicability gate

The root-owned 85-request degree-one panel was scanned on CPU14 without
executing msolve. Cumulative counts were 85 request-contract records, 20
reversible QQ covers with equations at least variables, 18 endpoint/proposal
compatible covers with a structural equation-variable perfect matching, and 9
records inside every frozen degree/cost cap. These represent 9 anonymous source
hashes and 9 anonymous structural signatures, passing the preregistered 4-hash /
2-signature recurrence gate.

The output contains only cumulative counts and signature cardinality. It emits
no individual source path, source hash, target, signature, or record. The gate
uses a fixed scale-aware endpoint target box, and fixed caps for variables,
equations, predicates, polynomial degree, monomials, coefficient bits,
expression operations, input bytes, and minimum structural matching degree
product.

Frozen invocation:

```bash
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 taskset -c 14 \
  /home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  run_static_applicability.py \
  --requests /approved/repository-external/full-ordinary-bindings.json \
  --requests-sha256 FROZEN_BY_BENCHMARK_OWNER \
  --output STATIC_APPLICABILITY_RESULT.json --expected-cpu 14
```

## Frozen selected-execution runner (not executed here)

The original bounded runner was frozen against the activation-only degree-one
panel. The production repair retains its containment but replaces that seam
with full ordinary-proposal custody rows. Every selected request gets a fresh
process pinned to CPU14, a 30-second outer wall cap, a 2-GiB aggregate RSS cap,
4-GiB address-space cap, 3-GiB data cap, one native thread, and the shared global
benchmark and sole-CAS locks.

The child runs the digest-pinned msolve wrapper, exact rational box selection,
the existing FLINT irreducible-factor stage, the repaired lossless BigInt
transport, and the existing Nemo QQBar source replay. Conversion is recorded
only when the untouched construction/constraints, guards, bounds, branch
selectors, and raw target link all pass exact replay.

The worker verifies source bytes/SHA, exact Float64 endpoint bits/SHA, complete
ordinary wrapper bytes/SHA, copied attempt canonical bytes/SHA, and original
result bytes/SHA. It also verifies the frozen RESULT/PLAN schemas and their
truth-blind, source-unchanged, endpoint-unchanged provenance. It revalidates a
positive primitive square-free irreducible
degree-1/2/4 minimal polynomial, exact isolator, and zero-based ordinal among
the factor's real roots. The endpoint selects the RUR box and a unique exact
irreducible theta factor; the ordinary target never selects a RUR root. QQBar
then replays all source relations, guards, bounds, compiler definedness and
predicates, branch obligations, and exact raw-target equality.

The parent emits an exact request digest, run-binding digest, authorization
digest, and one-time token digest for every fresh child. The child emits only a
`PARENT_ACCEPTANCE_REQUIRED` conversion candidate, and the aggregate counts it
only after independently matching all four digests. Direct child execution can
never emit authority. Parent and child also fail closed on any change to their
candidate-local runtime dependency hashes.

Converted artifacts set `ordinary_full_proposal_binding=true` but retain
`authority_pass=false`, `target_release=false`, and
`completeness_claim=NOT_MADE`. Each conversion is one descriptor only.

Individual request, source, target, failure, CAS, and replay artifacts remain in
the root-owned directory outside Git. The public JSON contains only cumulative
stage counts, converted count, anonymous converted-signature cardinality, and
false-authority count. The preregistered advance threshold is at least 3
conversions, at least 2 signatures, and false-authority count 0.

Benchmark-owner invocation (the raw directory must not already exist):

```bash
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 \
  MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  JULIA_NUM_THREADS=1 taskset -c 14 \
  /home/kabatan/work/solver/.venv/bin/python run_selected_execution.py \
  --requests /home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1/selected9-full-ordinary-bindings.json \
  --requests-sha256 FROZEN_BY_BENCHMARK_OWNER \
  --raw-output-dir /home/kabatan/work/solver-artifacts/EXP-V15-243-001/MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1/SELECTED_EXECUTION_RUN_001 \
  --output /home/kabatan/work/solver-artifacts/EXP-V15-243-001/MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1/SELECTED_EXECUTION_RUN_001_PUBLIC.json \
  --expected-cpu 14
```

No msolve, FLINT factorization, Julia/Nemo worker, formal scorer, truth, full98,
validation, or sealed evaluation was run while preparing this freeze.

## Production connector saved/generated D0

CPU14 D0 on Python 3.12.11 passed 12/12 pytest checks. Four frozen ordinary
artifacts passed full
bytes/SHA binding and the production selected-admission seam. Generated
degree-1, degree-2, and degree-4 descriptors passed the same primitive,
square-free, irreducible, isolator, and ordinal contract. Degree 3 and a
4,097-bit coefficient were rejected by the frozen cap. The already
saved RUR factor and QQBar replay chain passed exact byte links and count
ledgers.

Wrong factor, factor-local ordinal, branch/guard count, and complete ordinary
proposal bytes SHA mutations all failed closed. Additional mutations cover the
parent request/token binding, compiler definedness/branch accounting, and stale
candidate-local dependency hashes. The result records
`msolve_runs=0`, `julia_runs=0`, `authority_pass=false`,
`target_release=false`, and no completeness claim. Cap relaxation is not a
reopen condition. The only next gate is the benchmark-owner selected-nine
pilot using full ordinary artifacts; only after it may typed-guard Repair A be
considered.

Production mechanism hash:
`675d30505376f810db5582794ba60ab1fcdfb910a77ab3f12cbb392f62748593`.
The historical `FREEZE.json` remains unchanged; the full connector closure is
recorded in `PRODUCTION_CONNECTOR_FREEZE.json`.
