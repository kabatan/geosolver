# GeoSolver product requirements

- Python 3.12 and the packaged Julia/Nemo project are required. `doctor` verifies imports, Julia/Nemo evaluation, engine integrity, and a positive-dimensional smoke problem.
- The canonical public input is `GeometryProblem` JSON with `variables`, `constructions`, `conditions`, and `target`.
- `standard` runs natively on Linux, Windows, and macOS. `reference` is deterministic, Linux-only, fixed to one core and 180 seconds, and never falls back silently.
- API, CLI, HTTP, schemas, and the frontend use the same strict models. JSON booleans are not accepted as numeric scalars, and integer/float identity is preserved.
- A normal `no_answer_found` result is permitted only after a worker completed successfully. Process failure, missing or invalid artifacts, and no-progress termination are structured engine errors.
- Exact answers are either algebraic root descriptors or affine rational combinations of pi. Approximate proximity only orders work; canonical exact descriptors decide equality.
- Every solve session owns its worker and cancellation state. Cancelling or timing out one session cannot terminate another session.
- The HTTP server binds to loopback and uses a same-origin session cookie. Concurrent jobs remain independently cancellable.
- The UI preserves explicit constructions, conditions, and target expressions; it never infers mathematical constraints from appearance.

## Completeness and release validation

- Numerical search does not prove completeness. Such results report `completeness: unknown` even when one or more answers are found.
- Linux descriptor parity between `standard` and `reference` is a release gate. The complete 145-case comparison and experimental evidence live on the experiment branch, not on `main`.
