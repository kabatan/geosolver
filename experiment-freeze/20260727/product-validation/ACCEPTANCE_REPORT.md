# GeoTarget product acceptance — 2026-07-27

## Frozen identities

- Product commit: `00a067a63b3d`
- Champion closure: `9fa23aecdb9372dfd961b46224b88937c3317eaeb56796a05142563f26078f15`
- Dataset SHA-256: `e587c6ea3f315f270e13cae859bba947f52e59afb651b7485061fdc49be06b8f`
- Development-145 subset SHA-256: `b912d3fcd0a40e1de11d4c793c565a51d4eb5f33651ca4931eb30fcef6e4fced`
- Frozen comparison: 131/145 exact-set equal to truth, extra 0.

## Product run

The product was run on the same host with seven independent one-core lanes,
each pinned to the same physical CPU ordinal used by the frozen run. Every
case used 180 seconds, 256 starts, 600 callbacks/start, aggregate cap 153600,
and seed 0. No benchmark truth was available to the product process.

The run began from the same main implementation before its final commit amend.
The later amendments affected only the UI, process-tree cancellation, and
exhausted zero-dimensional continuation bookkeeping; the one-core,
180-second positive-dimensional execution path used here was unchanged.

- Cases completed: 145/145
- CLI/process failures: 0
- Cases returning at least one exact descriptor: 10
- Total returned descriptors: 11
- Descriptor sets identical to the archived frozen run: 21/145
- Archived frozen descriptors missing from the product rerun: 127
- Product descriptors absent from the archived frozen run: 1 (OMC101(F)); the
  archived truth score says that frozen case was missing one algebraic target,
  so this is not evidence of a false exact result.
- Product median: 175.079 s; frozen median: 138.069 s (+26.8%)
- Product p95: 177.807 s; frozen p95: 177.041 s (+0.43%)

## Acceptance decision

The one-time 145-case gate **does not pass**. It misses the required 131/145
truth equality, loses descriptors returned by the frozen run, and regresses
median wall time by more than 5%. Timeout/crash remained zero. No algorithm
knob, threshold, proposal order, precision, HP policy, restoration rule, or
exact-authority rule was changed to conceal or rescue this result.

The case-level evidence shows that a wall-clock-bounded rerun of the frozen
numerical algorithm is not result-stable under the seven-lane workload on the
current host state. The product engine and source hashes match; a separately
isolated case 001 run returned the same `x - 40` descriptor as the archive,
while the seven-lane product run did not. Treating the archived 131 result as
a deterministic release contract is therefore unsupported by the observed
evidence.

## Other acceptance checks

- Locked clean-wheel install, `doctor`, and smoke solve: pass.
- Zero-variable exact route: `x - 5`, exact complete, pass.
- 300-second exhausted-queue example: returned in about 1.45 seconds, pass.
- 300-second pending-work example: continued frozen start ordinals and
  preserved a consistent checkpoint, pass.
- Two-core HP wave: used CPU 8/9 in ordinal order and returned the same exact
  descriptor, pass.
- CLI interrupt: descendants in independently created process sessions were
  terminated; no worker leak remained, pass.
- Frontend TypeScript/Vite build and static-host tests: pass.
- Browser/Computer Use: point placement, catalog modal, JSON/constraint/target
  controls, and console-error check: pass (0 browser errors).

Raw per-case artifacts and temporary runners remain outside `main` in this
directory. Only this aggregate report, its checksum, and the paired aggregate
JSON belong on the `experiment` branch.
