# Source-only check ledger

Date: 2026-07-31 (Asia/Tokyo)

All Python checks were pinned to CPU 15.  No worker `--execute`, scorer, truth,
real-case artifact, validation, sealed input, or formal CPU 0..6 was used.

- `audit_seam.py` completed against the hash-bound current-campaign closure.
- The audit proved 8/9 required local fields; the missing field is a runtime
  branch token.
- The callback/aggregate structure proved 0/2 required anonymous churn strata
  because it retains only the latest assessed endpoint plus counters, not
  accepted-anchor/ordinary-trial transitions.
- Same-callback additional-source-valid-proposal telemetry is absent, so the
  D0 fixed-cap caveat remains open.
- Candidate audit plus the unchanged progressive/exact-outer unit suite:
  `12 passed` (`0.59 s`; two pre-existing Python AST deprecation warnings).
- `sha256sum -c HASHES.sha256`: all recorded files passed before this ledger
  was added.

No synthetic cut-bundle activation was run after the gate failed; doing so
would not repair the missing current-campaign attribution surface.
