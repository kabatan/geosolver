# EXP-GEOMETRY-KERNEL-001: geometry callback kernel optimization

This result records the bounded promotion decision for the geometry callback
optimization study. The experiment changed no solver code on `experiment` and
did not modify `main`. Large run outputs remain in the external artifact root;
this directory stores the reproducibility contract, decision, and checksums.

The compiled callback snapshot was semantically safe in the measured kernel
scope and reduced callback wall time by 7.25% (131 same-work cases, zero
differential mismatches). It was not promoted because the completed whole-
solver A1/B1 pair was correctness-neutral but 0.82% slower by the registered
geometric-mean wall metric. The five-seed serial ABBA campaign was interrupted
after B2 case 6/145, so no whole-solver speedup claim is made.

The external evidence root is:

`/home/kabatan/work/solver-artifacts/geometry-kernel/20260731-e5abe0-baseline`

See `result.json` for arm commits, frozen input hashes, report hashes, fixed
budgets, the partial-campaign boundary, and the cleanup scope. Do not copy the
external 145-case artifacts into Git.
