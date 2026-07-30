# SECTOR_CERTIFIED_INTEGER_ANGLE_RELATION_V1

- Hypothesis: current exact replay already proves the normalized unit complex of every nondegenerate direct `Angle`, but loses the lift when checking `m*Angle(...)=n*Angle(...)`. Exact sector certification can prove that the only possible full-turn lift is `q=0`.
- Mechanism: retain Repair A, run the current exact fallback first with at least 75% of the local budget, and reserve at most 25% for this side. A source-only scanner admits only `m*Angle(...)=n*Angle(...)`, with positive literal integers `m,n` in `1..3` and the same direct angle kind.
- Proof: recheck exact unit identity and principal domain `[0,pi]`; compare each cosine exactly against algebraic `cos(k*pi/m)` boundaries; reject boundary/tie; require equal strict sectors, which confines `m*theta-n*phi` to `(-pi,pi)`; then compare the exact unit-complex powers. Thus equality implies the unique lift `q=0`.
- Rejections: nonzero/ambiguous `2pi` lift, boundary, coefficient outside `1..3`, negative/noninteger, mixed direct-angle kinds, full-circle/nonprincipal, nested arithmetic, supplement, and degenerate angle all fail closed.
- Custody/fallback: source, guards, branches, raw target, minimal polynomial, ordinal, isolator, and numeric parity remain in the copied canonical replay. Side error/rejection/timeout returns the baseline mapping by object identity.
- Aggregate activation supplied by root: 44 attempts across 3 anonymous sources; source shapes include `Angle=2*Angle`, `2*Angle=Angle`, and one source containing both `2*Angle=Angle` and `3*Angle=Angle`. No row, ID, value, result, truth, or formal corpus was accessed here.
- D0: executable QQBar accept for `(m,n)=(1,2),(2,1),(1,3),(3,1)`; exact rejection of wrong `2pi` alias, sector boundary, supplement, and degenerate; product commutation and side swap metamorphic checks; 37/37 combined tests pass on the currently assigned CPU 14.
- Formal status: not run. Root benchmark owner must evaluate the fixed worker.
