# Real frozen-champion seam smoke

Truth-blind source smoke, `5 s`, `8 starts`, `100 callbacks/start`, CPU 31,
Python 3.12.11 / NumPy 2.5.1 / SciPy 1.18.0.

The first connection used frozen-AD support as the smoothness gate.  It had
`2` side lanes but `0` activations because the intentionally thin AD marks even
smooth geometry primitives unsupported.  Repair A changed the representation
gate, not a numerical threshold: source expressions with explicit nonsmooth or
branch tokens fail closed; unsupported smooth operations may use the existing
full-rank FD/direct-Broyden model.

| aggregate | frozen control | repaired candidate |
|---|---:|---:|
| lanes / safe endpoints | 8 / 8 | 8 / 8 |
| callbacks | 109 | 109 |
| invalid / guard-failed / exceptions | 0 / 0 / 0 | 0 / 0 / 0 |
| frozen / side lanes | 8 / 0 | 6 / 2 |
| spectral linearizations / activations | 0 / 0 | 17 / 5 |
| wall seconds | 0.616 | 0.643 |

No truth, target, expected count, family, or prior outcome was available.  The
source bytes stayed unchanged.  This is an activation/integration smoke only,
not a recall or speed claim.  Raw artifacts are outside Git at
`/home/kabatan/work/solver-experiment-results/spectral-cosh-real-smoke-v1/`.

## Current progressive-adaptive worker

The candidate-private entrypoint now loads the hash-pinned current adaptive
full wrapper and redirects only its search executable back to the same thin
entrypoint. The child retains the current scheduler and selects spectral-cosh
only for original start ordinal `3 mod 4`; repeated rungs preserve that route.

CPU-31 in-process source-seam tests passed `14/14`. They covered dependency and
arm hashes, current full-worker authority custody, 6/8 baseline and 2/8 side
routing on a synthetic eight-start prefix, unchanged source program, guarded
case, literal prefix and absolute deadline objects, rank/eigenframe and
nonsmooth fallback, source smoothness gating, and byte-identical canonical
serialization when activation is zero. The 37-case generated D0 aggregate was
also reproduced in substance (`17/0` wins/losses, zero false/extra, 75/25
routing). No subprocess benchmark, truth, scorer, case outcome, validation,
sealed or holdout input was used.
