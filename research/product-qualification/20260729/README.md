# Product qualification harness snapshot

These files are the one-off, identity-free compiled-kernel and same-work
qualification harnesses developed before the optimized product implementation
was frozen. They are intentionally not installed with GeoTarget and are not
part of the solve path.

The source snapshot is kept on `experiment` so the main branch contains only
the compiled evaluator, runtime adapters, public interfaces and permanent
regression tests. Full 145-case runs and profiler output remain in the external
artifact archive rather than Git.
