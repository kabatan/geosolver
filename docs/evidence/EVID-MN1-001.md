# EVID-MN1-001 — Independent repository bootstrap

Recorded: 2026-07-10  
Milestone: M-1

## Verified state

- Resolved repository root: `C:\solver`.
- Git metadata is a normal local directory: `C:\solver\.git`.
- Sole long-lived branch: `main`.
- Root commit: `474915315c4d8c870867a2c0fb3d4aa46c1bfb71`.
- No remote is configured.
- The new root commit has no parent, graft, replace, submodule or imported old
  Git objects.
- The old external repository was not edited or imported and is not referenced
  by build, test or runtime configuration.
- Julia 1.12.6 and Python 3.12.11 were verified by `scripts/doctor.ps1`.
- Smoke CI passed after resolving and committing both dependency locks.

## Checkpoint

- Annotated tag: `m-1-clean-repo`.
- Bundle: `C:\solver-checkpoints\m-1-clean-repo.bundle`.
- SHA-256:
  `f485f0af8c435a39dbe28042291964ad07eca577b220983f271eebd15b30cf8f`.
- `git bundle verify` reports a complete history.

This evidence records only newly created repository state. It does not preserve
or import legacy source, history, dirty changes or run artifacts.
