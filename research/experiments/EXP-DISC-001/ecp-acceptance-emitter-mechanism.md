# EXP-DISC-001 candidate C: ECP/ECPv2 acceptance emitter

Status: experiment-local comparator; no production or answer authority.

## Primary sources and exact adapter

- ECP: Fourati et al., *Every Call is Precious: Global Optimization of
  Black-Box Functions with Unknown Lipschitz Constants*, AISTATS 2025
  ([PMLR paper](https://proceedings.mlr.press/v258/fourati25a.html)).
- ECPv2: Fourati, Alouini, and Aggarwal, *ECPv2: Fast, Efficient, and
  Scalable Global Optimization of Lipschitz Functions*, AAAI 2026
  ([AAAI paper and DOI](https://ojs.aaai.org/index.php/AAAI/article/view/41018)).
- Authors' implementation: [`fouratifares/ECP`](https://github.com/fouratifares/ECP),
  inspected at commit `f4b2c7b949fb0053202a585bbaacd6119d95785b`, in particular
  `optimizers/ECP.py`, `optimizers/ECPv2.py`, and `utils/utils.py`.

The papers and official code maximize a scalar reward. GeoTarget screens a
scaled residual vector, so this adapter defines

```text
rho(x)    = ||scaled_residual(x)||_2
phi(x)    = rho(x) / (1 + rho(x))       if canonical-valid and finite
phi(x)    = 1                            otherwise
reward(x) = -phi(x).
```

`stable_phi` evaluates the same expression without overflowing and sorts
residual magnitudes before summation, making the score invariant to residual-row
permutation. It lies in `[0,1]`; every public floating field is finite or null.

Given explored points `x_i`, rewards `f_i`, and a caller-supplied normalized raw
candidate `x`, the official ECP acceptance inequality is used without a sign
shortcut:

```text
min_i (f_i + epsilon * ||x - x_i||_2) >= max_i f_i.
```

The first raw point is unconditionally screened. A later raw draw is screened
only if this inequality holds. Rejected raw draws are unscored and are not
proposals. Every screened point, including an invalid point or callback failure,
is retained as a proposal. No result field has answer, target, Gold, or
completeness authority.

## Fixed arms and budgets

Both arms use `epsilon_0=1e-2`,
`tau=max(1 + 1/(48d), 1.001)`, `C=1000`, a 48 accepted-screen cap, and a
65,536 raw-draw cap. The module performs no random draw and copies the caller's
`d x N` matrix; columns must be finite normalized coordinates in `[-1,1]^d`.

- `ECP_V1`: the ECP recurrence and full evaluated archive.
- `ECP_LB_FULL`: ECPv2's adaptive lower bound with `m=t` (the entire archive),
  no projection (`delta=0`, identity metric), and normalized-cube diameter
  `2sqrt(d)`. After a noninitial accepted screen it uses
  `max(epsilon*tau, (maximum(reward)-minimum(reward))/(2sqrt(d)))`.

The full archive and identity metric intentionally remove ECPv2's memory and
random-projection axes from this comparison. With at most 48 evaluated points,
their scalability benefit is not relevant, while exact Euclidean distances are
needed for transported signed-permutation/orthogonal replica tests.

If the accepted-screen cap is not filled, each missing logical slot is returned
as a typed `source=:fresh_iid` fallback request. Exhausting the source matrix and
hitting the 65,536 hard cap have distinct reasons. Actual screened callbacks plus
fallback requests always equal 48. The caller, not this module, materializes the
fresh IID points and charges their screens.

## Paper Algorithm 1 recurrence and official-repository deviation

The paper, rather than the repository's deque code, is the authority for the
growth recurrence. After the unconditional `x_1` evaluation, Algorithm 1 sets
`h_previous=h_1=1` and `h_current=h_2=0`. In each later evaluation round it:

1. samples a raw candidate and increments `h_current`;
2. **before acceptance**, if `h_current-h_previous > C`, multiplies epsilon by
   tau and resets `h_current=0`;
3. checks acceptance with that possibly increased epsilon;
4. if accepted, screens the point, assigns `h_previous=h_current`, advances
   epsilon for the next round, and resets `h_current=0`.

Thus this is not a fixed window of 1001 consecutive rejections. If a completed
round records `h_previous=5`, the next growth occurs at `h_current=1006`, because
the inequality is strict. Diagnostics expose the final previous/current `h`
states and growth count as finite integers.

At official repository commit
`f4b2c7b949fb0053202a585bbaacd6119d95785b`, both optimizer files instead start
with a length-one `deque([1])`, mutate its only entry, and compute a slope whose
denominator is `len(deque)-1`. The first rejected candidate before the second
evaluation therefore encounters a zero denominator; it also does not faithfully
represent Algorithm 1's two `h` states. This adapter does not emulate that defect.

Tests pin the paper order and state dependence: the first rejection has
previous/current `h=1/1` and no division; a completed `h=5` round distinguishes
the 1001st from the 1006th next-round draw; a boundary fixture is accepted only
because growth happens before acceptance. A separate 65,537-column fixture pins
termination after exactly 65,536 consumed raw draws.

## Pre-outcome V1/LB counterexample and arm recommendation

The counterexample was fixed as a mechanism test, not mined from benchmark
outcomes:

```text
domain:       [-1,1]
residual:     min(|x+0.5|, |x-1|)
raw prefix:   -1, -0.5, then 62 copies of 1
roots:        -0.5 and 1, with equal depth zero
```

Pre-outcome decision rule: recommend `ECP_LB_FULL` as the single formal ECP arm
iff it screens representatives of both equal-depth zero basins while V1 does not,
without exceeding 48 screens, discarding screened evidence, or changing any
authority/accounting invariant. Otherwise recommend the simpler `ECP_V1`.

Re-evaluated standalone result after replacing the fixed-window interpretation
with paper Algorithm 1 (no rejection growth is reached inside this 64-column
fixture):

| arm | screened raw indices | zero-basin coverage | fallback slots |
|---|---:|---:|---:|
| `ECP_V1` | `1,2` | only `-0.5` | 46 |
| `ECP_LB_FULL` | `1..48` | `-0.5` and `1` | 0 |

The gate therefore recommends **`ECP_LB_FULL` as the one formal experiment
arm**; `ECP_V1` remains a diagnostic ablation. This is not production promotion
evidence. The fixture exposes the general mechanism: the adaptive lower bound
can prevent an early mediocre observation from making a distant equal-depth
basin permanently unpromising at a finite raw budget.

## Assumptions, non-transferable guarantees, and break conditions

ECP's guarantees concern global optimization/simple regret for a scalar
Lipschitz objective over a compact domain with the paper's random exploration
assumptions. ECPv2 preserves those guarantees under its stated memory/projection
conditions. GeoTarget does not automatically satisfy those premises:

- guards, invalid domains, and branch changes can make `phi` discontinuous;
- an arbitrary caller stream need not have IID full support;
- finding one best scalar value is not the same as recovering every target or
  every close/equal-depth root;
- assigning invalid observations `phi=1` is safe accounting, not a Lipschitz
  extension or an existence proof;
- the normalized cube is invariant under signed permutations, but an arbitrary
  orthogonal map must transport the domain/candidate stream as well as the
  callback; it need not map the whole cube onto itself;
- this adapter's `m=t`, exact-distance arm does not claim the wall-time scaling
  of ECPv2's bounded memory and random projection.

Consequently, neither paper's regret theorem is claimed for this emitter. The
permanent bounded-gap independent-uniform insurance lane must remain outside it.

Kill the candidate before production promotion if any equal-work test shows:

- full-target work or close-root recovery no better than the preregistered
  discovery control;
- raw-cap fallback starves or changes the independent-uniform insurance prefix;
- screened evidence is discarded or a rejected draw is accidentally screened;
- invalid-moat or all-invalid inputs produce false answer/completeness authority;
- residual-row, signed-permutation, or transported orthogonal replicas change the
  answer class beyond prescribed numerical tolerance;
- gains occur only on the twin fixture or one named family rather than at least
  three unrelated families/the predefined discovery stratum.

The implementation and tests are deliberately isolated in this experiment. If
the formal arm fails its preregistered equal-work gate, remove it rather than add
case-specific routing or knobs.
