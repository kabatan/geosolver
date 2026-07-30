# EXP-PARTICLE-CONSENSUS-001 — equality-forced few-particle consensus

Status: `D0_PASS_GENERATED`; real 145/243 authority is `HOLD`.

Hypothesis: an 8-particle, 25%-budget side lane can reach disconnected roots
that ordinary consensus misses by combining Gibbs consensus with a stiff force
for `G(x)=0.5||F(x)||²`. The step is
`dz=-(I+h_c I+h_f J'J)^-1(h_c(z-m)+h_f J'F)`: the Gauss--Newton part is the
stable linearized semi-implicit approximation to Carrillo, Jin, Zhang, and Zhu,
*An interacting particle consensus method for constrained global optimization*
(2024), https://arxiv.org/abs/2405.00891 (eqs. 3 and 31).

Novelty/reopen: prior PolarCBO used localized merit-weighted Euler--Maruyama
transport and no equality force; SVGD used score attraction plus kernel
repulsion. This candidate adds a per-particle source-residual normal force and
its semi-implicit Gauss--Newton stabilization. It is not PRFC: there are no
factor blocks, persistent block copies, projectors, or reflections. Thus the
recorded “population parameter is not a new lineage” objection does not apply
to the new force law; plain CBO is retained as the direct side-lane ablation.

Frozen D0: 512 callbacks/arm; three unchanged 128-callback numeric lanes
(75%) plus one 128-callback side lane. Candidate and control execute exactly
the same callback count. The side lane has 8 particles and 15 steps; control
uses consensus only. Analytic row scaling and source chart scales make the
mechanism insensitive to residual permutation/sign/units and signed-permuted
coordinate units. Opaque/nonsmooth evaluators take an identical fourth numeric
fallback lane. No ID, family, source, truth, target, or prior outcome is visible.

Gate: at least three positive/negative/fallback families; activation; callback
parity; baseline quota >=75%; fresh full residual+guard replay; false/extra/loss
zero; strict gain; permutation/scale metamorphic parity. Failure reopens only
with a different force discretization or consensus topology, not radius/seed
tuning. No compiler, adapter, shared framework, or formal dataset is used.

D0 result: 190 fixtures / 380 arm runs, control 200 exact source-replayed roots
versus candidate 320 (`+120/-0`), with `+40` on each of three unrelated smooth
families. False/extra=0; all inconsistent fixtures emitted no root; all 30
opaque runs had byte-identical fallback outputs; all 40 permutation/scale
groups passed; every arm used 512 callbacks and exactly 75% baseline quota.
Initial fixed-consensus discretization tied 200→200. Repair A made the final
seven steps an equality-only increasing-stiffness implicit rung, removing the
off-manifold consensus bias; this changed the discretization, not a case
threshold, radius, or seed. Aggregate: `D0_AGGREGATE.json`.
