# Branching SVGD clean-room D0 algorithm card

## Decision and scope

**D0 decision: GO to a future connector audit, not to formal evaluation.**  The
prototype passed its predeclared generated gate in two of three anonymous
families.  It has no import, adapter, or data path to the formal execute,
scorer, manifests, truth, validation, or sealed corpus.  The formal harness was
not run.

This is a narrow mechanism prototype, not a particle framework.  The only
candidate-facing inputs are initial points, a log-density score callable,
source validity, source origin/scale, and a seed.  Generated exactification and
descriptor truth remain in `generated_cases.py`.

## Research basis and freshness

The transition follows the state construction in Bañales, Jaramillo, and
Ricalde-Guerrero, [Branching Stein Variational Gradient
Descent](https://arxiv.org/abs/2506.13916) (v2, 2025): particles have explorer
`E`, optimizer `O`, and unique-spine `S` colours; branching is followed by an
SVGD improvement; offspring are parent-conditioned; old particles survive and
become `O`; and a new spine is drawn uniformly.  The deterministic improvement
is the RBF update of Liu and Wang, [Stein Variational Gradient
Descent](https://arxiv.org/abs/1608.04471) (2016).

Repository source inspection found no mathematical duplicate.  The old
`annealed_svgd_root_emitter_v17` is fixed-population deterministic SVGD.  The
earlier `epoch_d_stein_particle_portal_precode_stop` correctly stopped another
fixed-population update as a duplicate, but explicitly recorded random
branching as absent.  See `PRIOR_OVERLAP_CARD.md`.

## Frozen clean-room mechanism

- Start with four particles: three `E`, one uniformly selected `S`.
- Perform one deterministic RBF-SVGD improvement, then seven
  branch/improve generations.
- `E` offspring count is Bernoulli(0.5), `O` offspring count is exactly zero,
  and `S` offspring count is uniform on `{1,2,3}`.
- Children are `E` and sampled from a parent-centred Gaussian with normalized
  standard deviation 0.85.
- Every old particle is retained, recoloured `O`, and preserves identity;
  deaths are forbidden.
- Exactly one particle is selected uniformly from the full post-branch
  population and recoloured `S`.
- Score and RBF geometry operate in dimensionless source coordinates.  Invalid
  or non-finite moves are rejected, never clipped into validity.
- Final descriptors are emitted only after generated exactification, source
  replay, semantic validation, and set deduplication.

The numerical constants above were selected once before the decision panel.
No grid, case-conditioned tuning, family routing, problem ID, geometry name, or
answer value is present.  The paper supplies the role transition, but the
Bernoulli explorer law and constants are explicitly this D0's clean-room
configuration, not claims about a paper default.

## Controls and quota

Each portfolio has four lanes.  Three lanes always run the old deterministic
fixed-population SVGD; only lane four changes, giving an exact 75% baseline / 25%
side quota.

1. `old_deterministic`: four fixed-population SVGD lanes.
2. `count_matched_immigration`: three fixed lanes plus memoryless immigrants
   sampled around the original centroid.
3. `branching_svgd`: three fixed lanes plus the role-coloured branch process.

For every case the branching and immigration side lanes have identical
population counts at every generation and identical score-call counts.  Thus
the comparison distinguishes parent-conditioned multigeneration descent from
merely buying the same number of random particles.  The old deterministic arm
is intentionally cheaper; this is a recall mechanism test, not a speed claim.

## Generated panel and gate

The fixed panel contains 204 runs across three structurally different,
anonymized multimodal families:

- 48 identity positive runs (16 seeds per family);
- 18 single-root negative runs;
- 18 multiwell near-miss runs whose non-primary exact roots are semantically
  invalid;
- 120 positive metamorphic runs covering variable permutation, reflection,
  rotation, and affine scales 0.2 and 7.

GO was fixed as: gain against both controls, loss zero, and positive aggregate
descriptor delta in at least two anonymous families, plus safety, activation,
and metamorphic passes.

## Result

Two anonymous families qualified:

| family | versus old (g/l, root delta) | versus immigration (g/l, root delta) |
|---|---:|---:|
| `family-6e85ebe7` | 5/0, +6 | 5/0, +6 |
| `family-8c4bc1c2` | 2/0, +2 | 2/0, +2 |

`family-7671186e` improved over old by 7/0 (+7) but had 7/1 (+6) against
immigration, so it did not qualify.  Across all positive presentations,
descriptor totals were 215 branching, 178 immigration, and 168 old.  Totals
are secondary; the family-wise zero-loss gate controls the decision.

Safety and activation:

- invalid emitted: 0; crashes: 0;
- negative and near-miss branching output was always the one valid primary
  descriptor;
- generated semantic replay rejected 10 provisional invalid candidates before
  emission;
- accepted offspring: 2,829 from `S`, 2,511 from `E`, 0 attempted from `O`;
- old-particle retention events: 21,534; deaths: 0;
- mechanics tests passed exact unique-spine, ID retention, quota, uniform-draw
  envelope, and SVGD permutation/reflection covariance.

The aggregate stochastic metamorphic deltas were within 0.1875 descriptor of
identity (the frozen D0 tolerance was 1.0).  Exact deterministic SVGD direction
covariance was separately checked at `2e-14` tolerance.

## Reproduction and boundaries

Run only on allowed CPU 15:

```bash
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  taskset -c 15 /home/kabatan/work/solver/.venv/bin/python -m unittest -v test_candidate.py
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  taskset -c 15 /home/kabatan/work/solver/.venv/bin/python run_generated.py \
  --output D0_RESULT.json --raw-output /tmp/branching-svgd-d0-raw.json
```

Recorded environment: Python 3.12.11, NumPy 2.5.1, one Python process, one
native thread, affinity CPU 15.  Raw rows are outside Git at
`/home/kabatan/work/solver-artifacts/branching-svgd-cleanroom-d0-20260731/raw_rows.json`;
their SHA-256 is in `D0_RESULT.json`.

## Limits and next gate

The generated landscapes are low-dimensional multimodal score surrogates, not
geometry problems.  Capture exactification is generated-test infrastructure.
This evidence does not establish 145/243 recall, speed, p95, or integration
safety.  A next step would need a separate, source-only connector audit that
derives a score from ordinary residual/Jacobian information, preserves the
same 75/25 quota, and still keeps all candidates behind canonical source
replay.  No formal run is authorized by this card.
