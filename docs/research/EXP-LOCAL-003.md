# EXP-LOCAL-003 — semantic-preserving local model scaling

Status: **card-only preregistration**. No generator, mechanism source, input or
result exists for this experiment at this commit. The machine-readable
authority is [`EXP-LOCAL-003.json`](../../research/experiments/EXP-LOCAL-003.json).

The experiment keeps the current dense finite-difference LM-QR algorithm and
the open black-box callback fixed. If relation raw value is `y_i` and its
declared semantic scale is `s_i`, then

```text
z_i = y_i / s_i
```

is the only convergence, canonical-validation and Gold-assessment residual.
`RelationObservation.raw`, `scale`, `scaled`, relation truth, guards, domains,
branches, target and wire bytes remain unchanged.

| Variant | Variable coordinates | LM model residual |
|---|---|---|
| `L0-SEMANTIC` | declared semantic origin/scale | `z` |
| `LX-BOUNDS` | finite-bounds midpoint/half-width | `z` |
| `LR-MODEL` | declared semantic origin/scale | `m_i = z_i/a_i` |
| `LXR-BOUNDS-MODEL` | finite-bounds midpoint/half-width | `m_i = z_i/a_i` |

LR/LXR receive the same 64 Gold-independent calibration points. A point enters
calibration only when the complete observation vector is status-valid and all
components of `z` are finite. With `K` valid vectors, `a_i` is the
`ceil(0.75K)` nearest-rank order statistic of `abs(z_i)`. If `K < 8`, or any
selected value is nonfinite or nonpositive, the joint fallback is `a_i = 1`
for every component. `a` is charged numerical-model state only; it is never
written into the DSL, plugin ABI, `RelationObservation` or protocol wire.

Development contains eight unrelated families, two latent groups per family
and three within-group representations: base, deterministic signed
variable/residual permutation, and positive row rescaling that multiplies
`y_i` and `s_i` together. This gives 48 cases. The 16 latent groups—not the 48
rows or 32 starts—are the inferential clusters. Family effects and positive
family count are descriptive.

Safety16 adds one frozen orthogonal representation per latent group. It is
reported separately and cannot improve a promotion statistic. Candidate and
Gold artifacts live in separate frozen trees; candidate execution cannot read
Gold, assessor tolerances, problem IDs or family IDs.

All variants use the same 32 starts and prefixes 8/16/32. Calibration, failed
starts and full local work are charged to recall and expected-runtime gates;
process CPU and host-valid wall time are secondary. There is no tuning round.
Only a complete development pass can authorize materializing the 96 fresh
locked cases (eight families × four new latent groups × three
representations). No card result can change the public DSL or remove the C0
fallback lane.
