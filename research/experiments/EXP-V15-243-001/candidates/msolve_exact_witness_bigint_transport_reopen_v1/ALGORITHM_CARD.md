# MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1

## Decision

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
  --requests /home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-requests.json \
  --requests-sha256 ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35 \
  --output STATIC_APPLICABILITY_RESULT.json --expected-cpu 14
```

## Frozen selected-execution runner (not executed here)

The bounded next-step runner is now frozen, but only the benchmark owner may
execute it. It rescans all 85 anonymous requests with the exact static predicate
above and launches only eligible requests. Every selected request gets a fresh
process pinned to CPU14, a 30-second outer wall cap, a 2-GiB aggregate RSS cap,
4-GiB address-space cap, 3-GiB data cap, one native thread, and the shared global
benchmark and sole-CAS locks.

The child runs the digest-pinned msolve wrapper, exact rational box selection,
the existing FLINT irreducible-factor stage, the repaired lossless BigInt
transport, and the existing Nemo QQBar source replay. Conversion is recorded
only when the untouched construction/constraints, guards, bounds, branch
selectors, and raw target link all pass exact replay. The degree-one projection
is not the complete ordinary proposal: every artifact therefore retains
`ordinary_full_proposal_binding=false`, `authority_pass=false`,
`target_release=false`, and no completeness claim.

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
  --requests /home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-requests.json \
  --requests-sha256 ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35 \
  --raw-output-dir /home/kabatan/work/solver-artifacts/EXP-V15-243-001/MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1/SELECTED_EXECUTION_RUN_001 \
  --output /home/kabatan/work/solver-artifacts/EXP-V15-243-001/MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1/SELECTED_EXECUTION_RUN_001_PUBLIC.json \
  --expected-cpu 14
```

No msolve, FLINT factorization, Julia/Nemo worker, formal scorer, truth, full98,
validation, or sealed evaluation was run while preparing this freeze.
