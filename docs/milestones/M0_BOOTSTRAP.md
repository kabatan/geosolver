# M-1 / M0 / M1 Acceptance Checklist

## M-1 — clean repository

- [x] `C:\solver` resolved and old working copy verified clean.
- [x] New independent `main` repository created without old history/code.
- [x] No remote configured; external old repository left untouched.
- [ ] Root commit, annotated tag and Git bundle checkpoint created.

## M0 — governance and toolchain

- [x] Charter, requirements, traceability, ADRs and research protocol written.
- [x] Julia 1.12.6 selected; Python requires 3.12 or newer.
- [ ] Julia/Python workspace skeleton and lock files committed.
- [ ] One cross-platform test entry point and CI smoke are green.
- [ ] Architecture fitness checks reject forbidden dependencies/patterns.
- [ ] Initial literature matrix and three preregistered experiment cards exist.

## M1 — ABI vertical slice

- [ ] Frozen registry with PluginSpec/PluginLock and C0/C1/C2/C3V/C3A report.
- [ ] Four graph node kinds, typed reference checks and deterministic JSON form.
- [ ] Opaque iterative custom call with a custom result type.
- [ ] Multi-valued Choice with stable key, selector margin and sibling branch.
- [ ] Equality relation, strict guard, domain and target remain separate.
- [ ] Reference evaluation works for Float64 and BigFloat when supported.
- [ ] Exact-capable demonstration carries separate config/target certificates.
- [ ] Python builder emits canonical JSON and invokes the Julia CLI.
- [ ] Differential, conformance, schema and negative capability tests pass.

