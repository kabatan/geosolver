# M-1 / M0 / M1 Acceptance Record

This is a historical foundation record, not the current project status page.
The active implementation status and limitations are maintained in the root
README and the traceability/evidence ledgers.

## M-1 — clean repository

- [x] `C:\solver` resolved and old working copy verified clean.
- [x] New independent `main` repository created without old history/code.
- [x] No remote configured; external old repository left untouched.
- [x] Root commit, annotated tag and verified Git bundle checkpoint created.

## M0 — governance and toolchain

- [x] Charter, requirements, traceability, ADRs and research protocol written.
- [x] Julia 1.12.6 selected; Python requires 3.12 or newer.
- [x] Julia/Python workspace skeleton and lock files committed.
- [x] One developer/CI test entry point and smoke tier are green on Windows.
- [x] Architecture fitness checks reject forbidden dependencies/patterns.
- [x] Initial literature matrix and preregistered experiment cards exist.

## M1 — ABI vertical slice

- [x] Frozen registry with PluginSpec/PluginLock and C0/C1/C2/C3V/C3A report.
- [x] Four graph node kinds, typed reference checks and deterministic JSON form.
- [x] Opaque iterative custom call with a custom result type.
- [x] Multi-valued Choice with stable key, selector margin and sibling branch.
- [x] Equality relation, strict guard, domain and target remain separate.
- [x] Reference evaluation works for Float64 and BigFloat when supported.
- [x] Exact answer protocol carries separate configuration/target certificates.
- [x] Python builder emits and validates canonical problem JSON.
- [x] Julia application accepts canonical JSON through an explicit registry.
- [x] Differential, conformance, schema and negative capability tests pass.

Python-to-Julia process transport was intentionally not hidden inside the
authoring package; applications own that boundary. See the SDK quickstart.
