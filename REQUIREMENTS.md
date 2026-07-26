# Product requirements

- Python 3.12, Julia 1.12.6, and the locked Nemo environment.
- Canonical input is champion-native V15 JSON only.
- Engine bytes are checked against the product manifest before every solve.
- `time_limit_seconds >= 180`, `cores >= 1`, and finite options are validated.
- API, CLI, and HTTP use the same models and normalized result contract.
- The HTTP server binds loopback, is same-origin, and serializes solve jobs.
- The UI never infers constraints from appearance; Fixed/Free/Derived,
  constraints, guards, branch/order, and target remain explicit.

## Frozen-engine limitations

- The reference worker currently supports `cores=1` only; larger values fail
  with `resource_error` instead of being silently downgraded.
- Requested time beyond 180 seconds does not create new starts or work. The
  frozen worker has no exported resumable checkpoint, so the result records a
  180-second used window and an explicit warning.
- The one-time paired 145-case product run is release validation, not a
  maintained benchmark suite, and is intentionally not stored on `main`.
