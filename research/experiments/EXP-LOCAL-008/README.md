# EXP-LOCAL-008 — poll-only OrthoMADS/extreme-barrier local comparator

This experiment is the preregistered local-algorithm branch taken after the external
Powell HYBR comparator failed its 48-case T2 gate.  It tests a mechanism that is
independent of the rejected interpolation-based DFO-LS candidate: there is no model,
search step, surrogate, derivative, or result-dependent fallback.

For finite bounds, physical coordinates are mapped to `u in [-1,1]^n`.  The only
objective seen by the candidate is

`phi(u) = 0.5 * sum_i (r_i(x(u)) / residual_scale_i)^2`.

Invalid bounds, semantics, nonfinite output, and domain exceptions have merit `+Inf`
(the extreme barrier).  They are never converted into a finite pseudo-residual.

At mesh index `ell`, the `t`th prime-base Halton vector `h_t` is centered and
normalized.  Scaling and integer rounding produce `q` with maximal norm subject to
`||q||^2 <= 2^ell`.  The poll basis is

`H = ||q||^2 I - 2 q q'`, `D = [H, -H]`.

Thus `H'H = ||q||^4 I`: the columns are an integer orthogonal basis, not coordinate
polling, and the Halton tail changes their orientation deterministically.  Poll points
are `u + Delta_m d`, with `Delta_m=4^(-ell)` for positive `ell`.  The implementation
uses a complete 2n poll and strict merit decrease.  If the callback limit interrupts a
poll, its partial best is discarded before the solver returns `LOCAL_MAX_EVALUATIONS`.
The Halton index follows the original OrthoMADS smallest-so-far rule; it is not an
ad-hoc per-iteration counter.

The formula follows Abramson, Audet, Dennis, and Le Digabel,
[OrthoMADS](https://doi.org/10.1137/080716980).  Extreme-barrier behavior matches the
[NOMAD 4 user guide](https://nomad-4-user-guide.readthedocs.io/en/v.4.4.0/HowToUseNomad.html).

The prospective T0 contains Curved, NearRank, Tangent, both Warped target maps, and
the existing on-boundary StrictGuard counterexample: six cases and eleven targets.
At the 4,800 callback authority point, work is recomputed from raw common-assessor
attempt fields as the suffix-stable safe-full work for each case.  Misses and values
above 4,800 are right-censored to 4,800.  The older lab-safe-full field is not an
authority.  Both promotion paths require aggregate target/safe-full and exact-stratum
noninferiority, zero safety/accounting violations, StrictGuard safe-full, and at least
one qualified StrictGuard witness that recovered after an extreme-barrier evaluation.
Path A additionally requires a strict target or safe-full gain with work ratio at most
1.20; Path B instead requires work ratio at most 0.80.

The outcome must not be run until the source, tests, and `preregistration.json` are
committed and the root agent authorizes execution.  After authorization, a single
shard can be launched with:

```bash
JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-008 \
  research/experiments/EXP-LOCAL-008/run_t0.jl \
  --shard-index=0 --shard-count=6
```

The common wave driver launches all six shards for both EXP-LOCAL-008 and 009
on at most 12 distinct physical cores. Its aggregator independently rebuilds
the promotion metrics from raw attempts and requires both control arms to
match:

```bash
python3 research/experiments/EXP-LOCAL-008/run_t0_wave.py run --jobs=12
python3 research/experiments/EXP-LOCAL-008/run_t0_wave.py aggregate \
  --truth-leak-audit=pass --mechanism-tests=pass
```

Targeted tests are safe before outcome authorization:

```bash
JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-008 \
  research/experiments/EXP-LOCAL-008/test/runtests.jl
```
