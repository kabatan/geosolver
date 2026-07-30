# THEOREM_BOUNDED_KLL_RADICAL_POWER_TARGET_LINK_V1 — synthetic D0

- Hypothesis: a frozen 256-bit KLL proposal can be certified against an existing full-source regular-root box even when direct ideal membership fails, provided the fixed square relation `p(h)^2 = Σ a_i g_i` is supplied exactly.
- Mechanism: accept one degree 1–4, primitive height ≤2^20 proposal; require irreducible and square-free `p`; validate complete regular box `R`, all source equations/guards, exact cofactor expansion with link power only 1 or 2, generator vanishing on `R`, and a target interval containing exactly one real root. KLL/Groebner never grants authority.
- D0: 1,280 synthetic instances / 2,560 direct-vs-radical traces, seed 20260760, CPU 14. Positive families are `x²-r`, `g=f²` with square membership only, and coupled 2D with a proposal-omitted identity. Negatives cover wrong polynomial, fourth-power-only, reducible, two-root interval, discriminant zero, incomplete `R`, and mutated cofactor. Four variants test variable permutation, equation/generator scaling and permutation, and factor/expand representation.
- Result: positive 3/3; negative emit 0; false authority 0; metamorphic failure 0; KLL contract failure 0. Direct-link ablation differs only on `g=f²`: Groebner remainder of `h` is nonzero while remainder of `h²` is zero.
- Decision: **ADVANCE** to an eligibility-screened, truth-blind source gate. Synthetic-only; no corpus/formal/98 result was read and no 145/243 claim is made.

Reopen only if an eligible source already has a complete regular-root proof and a bounded exact cofactor square certificate; do not reopen for higher powers, interval ambiguity, or parameter sweeps.
