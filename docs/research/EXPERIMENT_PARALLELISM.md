# Experimental case parallelism

The primary Linux host exposes an AMD Ryzen 9 9950X3D with 16 physical cores,
two hardware threads per core, and 32 online logical CPUs. The topology was
read from `lscpu` on 2026-07-12; CPUs 0--15 are the first hardware thread of
cores 0--15 and CPUs 16--31 are their SMT siblings.

Parallelism accelerates independent research cases and seeds. It does not
change the computational resources available to one solve:

- each case process uses `JULIA_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
  `OMP_NUM_THREADS=1`, and `MKL_NUM_THREADS=1`;
- the default throughput launch uses at most 16 workers, one per physical
  core, with stable case/seed shards and deterministic merge order;
- each shard records its worker count, CPU affinity, inputs, environment,
  source revision, and output checksum;
- callback work and success metrics remain authoritative in a parallel run;
  per-case wall time is diagnostic because workers share caches and memory;
- finalist wall comparisons are repeated serially on the same host after the
  algorithm and configuration are frozen;
- using all 32 SMT threads requires a separate throughput calibration and is
  never presented as a one-case speedup.

This research-only process parallelism is distinct from the public
`worker_count` option. The latter remains disconnected from production
multistart until a finalist has passed correctness and determinism gates.

