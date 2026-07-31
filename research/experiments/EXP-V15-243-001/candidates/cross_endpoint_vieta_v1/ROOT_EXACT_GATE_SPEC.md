# Root-only exact gate

`root_exact_gate.py coordinator` is the sole panel entry point. It requires
CPU affinity `[14]`, the official
`/tmp/geotarget-exp-global-benchmark-v1.lock`, pinned Python and bounded-process
helpers, a caller-supplied self SHA, and paths below
`/home/kabatan/work/solver-experiment-results`.

The private manifest schema is
`geotarget.cross-endpoint-vieta-private-gate/v1` with `subsets` containing the
connector's v3 private subset records. Source groups and at most 16 subsets per
source are SHA-ranked; the panel is capped at 595 structural proposals. Every
subset runs in a fresh bounded process. No scorer or truth is available.

The aggregate gate is GO only when all worker processes are accepted, numeric
guard/branch parity is present for every row, factor parity activates at least
3 sources and 2 structural signatures, canonical endpoint replay also
activates at least 3 sources and 2 signatures, and safety invalidity is zero.
Whole-Vieta minimal descriptors, replay bypass, unobserved-root emission, or a
changed baseline union force STOP.

The required mode-0600 root-custody sidecar contains only distinct source
SHA-256 values whose bounded structural Vieta proposal was constructed. It
contains no control or canonical replay outcomes.
