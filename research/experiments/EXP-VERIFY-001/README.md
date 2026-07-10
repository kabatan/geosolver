# EXP-VERIFY-001 development-input scaffold

This directory freezes the source-only boundary for the first C3V experiment.
It contains no interval dependency, validated interpreter, Krawczyk
implementation, plugin callback, generated manifest, Gold value, or observed
outcome.

The governing bundle is:

1. `../EXP-VERIFY-001.json`;
2. `../../../docs/adr/0004-c3v-validated-interval-boundary.md`;
3. `input-boundary-amendment.json`;
4. the declarative files under `generator/` and `assessor/`; and
5. `preregistration-lock.json`, which binds the preceding sources by SHA-256.

The 48 development base cases are allocated before any mechanism exists:

- 24 regular composed cases;
- 12 domain/guard/branch cases;
- 8 singular/manifold cases; and
- 4 exact-input cases.

There are also 44 safety-only subtrials: 12 additional input-state trials, 24
artifact-replay trials, and 8 explicit-C3V capability trials. Subtrials never
enter the certification-rate denominator and never increase the 48-case
instance count.

## Required implementation order

1. Commit this source lock while no formal input or V1 source exists.
2. Pin the optional interval dependencies in a separate commit.
3. Implement content-locked research fixture callbacks from
   `generator/fixture-descriptors.json`. These fixtures may use the existing
   `OperatorKernel.validated` field, but `generic_numeric` is never an explicit
   validated callback.
4. Add a one-shot materializer. It must verify every hash in
   `preregistration-lock.json`, bind the pinned dependency and fixture hashes,
   reject an existing output tree, and reject any V1 mechanism or validated
   interpreter source.
5. Materialize candidate-visible and assessor-only trees in separate atomic
   destinations. Freeze both trees and their independent checksums.
6. Only then implement the validated-box interpreter, Krawczyk candidate,
   artifact encoder, and independent replay verifier.

The one-shot materializer is intentionally absent from this checkpoint. No
file in this directory is executable input preparation.

## Separation rule

The future candidate manifest contains only opaque ordinal IDs, the canonical
problem graph and plugin locks, an exact proof box, the frozen point endpoint,
and opaque safety-instruction IDs. Family, factors, eligibility, expected
decision, mutation meaning, VREF truth, and every Gold value live only in the
assessor tree. Candidate case checksums are computed from candidate documents
alone.

V1 may route on declared capabilities and runtime interval evidence. It may
not route on case IDs, fixture IDs, primitive names, family labels, or Gold.
The graph remains the open Literal/Reference/plugin-qualified Call/Select DSL;
no polynomial lowering is introduced.
