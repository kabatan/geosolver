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

## Next bounded step

Integrate this transport into the existing msolve exact-witness route and run a
truth-blind capability census under per-route quota. Do not allocate portfolio
authority merely from this one-job causal repair; each accepted descriptor must
still pass the complete canonical QQBar source replay.
