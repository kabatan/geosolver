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

## Next bounded step

Rerun the frozen static predicate inside a contained worker, execute msolve only
for the eligible anonymous subset under a strict route quota, and return each
candidate to complete canonical QQBar source replay. Do not allocate portfolio
authority from static eligibility alone.
