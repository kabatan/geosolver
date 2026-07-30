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

