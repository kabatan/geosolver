# Rational linkage robustness / physical feasibility review

2026-10-02. This subtask changed only `round2-fresh/robustness/` and left the existing linkage, HTML preview, repository solver, and other experiments untouched.

## Finding

Negative inversion constant is the useful improvement. Replacing the positive-K Peaucellier cells by `K < 0` preserves the reciprocal map while avoiding the `P = Q` coincidence at `|P-O|² = K`. The three collinear-pole construction is currently preferable to the equilateral complex-pole construction. Neither this change nor the numerical optimization establishes a new research result by itself.

For a cell with `OA = OC = L`, `PA = PC = QA = QC = S`, the construction satisfies `Q-O = (L²-S²)/conj(P-O)`. Taking `S > L` is a real rigid-link configuration, not a complex-coordinate relaxation. The model has 18 moving points, 36 coordinates, 26 distance equations, 8 scalar ternary-link equations, and 2 input-coordinate equations. All continuation experiments below solve these 36 physical-coordinate equations; root matching is used only for initial discovery/initialization.

The retained reference has poles `(-1,0,1)`, `K=-0.6`, `L=1`, `S=sqrt(1.6)`, pantograph arm `2.3958349462896438`, and physical input `D1=K*w/3`. A and B exchange states `(12)` and `(23)` respectively on the initialized three-sheet component. The root certificate uses arm `2.395834946`, a slightly different explicitly dyadic nominal model.

## Reproducible numerical evidence

All bar lengths and all four independent ternary-hole ratios are perturbed independently and simultaneously. These are randomized numerical tests, not all-tolerance guarantees. A failed Newton continuation is not a proof that the mechanism cannot move.

| Experiment | Real negative K | Equilateral negative K |
|---|---:|---:|
| Seed 202610025, ±0.1%, 12 trials | 12/12 | 12/12 |
| Same seed, ±0.3% | 12/12 | 12/12 |
| Same seed, ±1% | 11/12 | 10/12 |
| Same seed, ±3% | 2/12 | 2/12 |

A further 1,584 scalar-dimension candidates and 810 unequal-cell candidates were examined with a local sensitivity proxy. The proxy did not reliably improve actual tolerance. For example, reducing memory-joint local sensitivity from about 30.2 to 20.0 gave only 4/12 successful ±1% trials at seed 202610026, versus the reference's 10/12 on the same trials. This is evidence against selecting designs solely by local condition or sensitivity.

A refined triangular candidate was chosen before a separate held-out seed 202610028. That test also perturbs all six fixed-pivot coordinates independently by `±epsilon × minimum nominal anchor separation`, keeping the nominal uncalibrated control path fixed.

| Held-out test, 50 trials per level | Real reference | Refined triangle |
|---|---:|---:|
| All 36 manufacturing coordinates/parameters, ±1% | 46/50 | 43/50 |
| Same model, ±2% | 23/50 | 31/50 |

The triangular result does not justify replacing the real reference, particularly given its layer-routing failure below. Parameter settings, exact seeds, and individual success/failure stages are in `comparison.json`, `refinement_validation.json`, `reference_new_seed.json`, `anchor_validation.json`, and `heldout.json`.

## Layer routing: a real remaining engineering task

The geometric audit sampled 5,406 complete poses: two loops, 901 control vertices, three initialized states. It measured projected distances between every joint and every nonincident straight rod, including the full extent of each ternary rod.

| Quantity | Real reference | Refined triangle |
|---|---:|---:|
| Swept planar bounding box | 5.30 × 3.49 | 5.38 × 5.77 |
| Nonincident joint/rod pairs coming within .01 | 97 | 232 |
| Pairs coming within .04 | 127 | 233 |
| Minimum sampled projected distance | 1.16e-6 | 1.38e-7 |
| Static distinct-layer assignment, .01 threshold | feasible | infeasible |
| Static distinct-layer assignment, .04 threshold | feasible | infeasible |

The MILP assigns each of the 26 rods a different layer. For every close joint/rod pair, that rod must lie above all rods incident to that joint or below all of them. This models a straight vertical through-pin connecting all incident rod layers. At .04, a feasible real-reference rod layer assignment is:

`[17,16,20,23,25,24,13,10,15,9,8,11,18,21,19,12,22,14,3,0,2,1,4,6,7,5]`

The rod-index mapping is `RODS` in `clearance_audit.py`. HiGHS proved the triangular near-pair MILP infeasible under this restricted geometry; this does not rule out bent rods, alternative joint designs, or a different layout.

A feasible order is **not a physical collision certificate**. It is based on sampled poses and excludes rod thickness, joint bodies, pin/pin collisions, elastic deflection, and the extension of ground pins to a support frame. Stacking all 26 rods is an existence diagnostic, not a compact CAD design.

### Added support-frame feasibility check

The **original real negative-K baseline** above was subsequently checked at the same .04 threshold, using the saved 5,406-pose near-pair data. This does not cover the later bias/capsule designs or their changed dimensions. There are five near nonincident rods at each fixed anchor O0/O1/O2, hence 15 anchor/rod pairs. Each anchor is incident to two rods: O0 to rods 0 and 3, O1 to rods 6 and 9, and O2 to rods 12 and 15.

For an anchor pin extending upward from a plate below every rod, each near nonincident rod must be above both incident rods. For a pin extending downward from a frame above every rod, each near nonincident rod must be below both incident rods. The existing constraints for moving through-pins and all 26 distinct rod layers were retained.

| Support arrangement | MILP result | Solve time |
|---|---|---:|
| All three anchors from a common bottom plate | infeasible | 0.011 s |
| Each anchor independently selects bottom or top frame | infeasible | 1.093 s |

The first model has 478 variables and 1,342 constraints. The second adds three anchor-side binary variables and has 1,372 constraints. HiGHS reports infeasibility in both cases, rather than a timeout. An independent integer check confirms that the previously saved .04 layer order satisfies all ordinary through-pin constraints but violates 13 anchor support constraints under the common-bottom condition.

Thus, this straight-rod, distinct-layer, straight-through-pin construction cannot simply be mounted to the proposed common bottom plate or split top/bottom frames under the sampled .04 near-pair model. This result does not rule out different pin constructions, offset supports, bent rods, or a changed mechanism. It neither provides continuous-path clearance certification nor assesses frame structure, controlled-D1 support, pin/pin collisions, or mechanical stiffness. Reproduction and raw results are in `support_layer_audit.py` and `support_layers_0.040.json`.

### Concrete support-routing rescue

An additional model allowed the two fixed links at each O-anchor to have separate coaxial bearings, with each of the six links independently supported from the bottom or top plate. Removing the common O-shaft requirement still resulted in MILP infeasibility (0.875 s). The result is recorded in `split_bearing_rescue_0.040.json`.

A more flexible **stationary support architecture does pass a sampled centerline check**, preserving the original nominal trajectories and the original 26-layer order. For each fixed rod in layer h, use a short stationary bearing stub from h to h+0.5. A rigid planar support arm at h+0.5 runs to an exterior post. The post lies outside the entire sampled planar swept bounding box and connects to an external support frame. The two fixed links at an O-anchor therefore retain the same projected fixed rotation center without a common shaft traversing the space between their layers. Moving joints retain the existing through-pins. No moving link outline or nominal hole position is changed.

The problematic projected anchor/rod pairs at .04 were O0 with rods {6,7,8,20,21}, O1 with {4,13,19,21,25}, and O2 with {9,10,11,23,25}. The long ground columns caused the obstruction; short stubs plus arms avoid those columns. The route planner placed each arm between rod planes and treated every moving pin whose layer interval crossed that height as a swept planar obstacle. Grid search proposed routes, which were simplified only after direct point-to-segment checks against every sampled pin position.

| Anchor / fixed rod | Support-arm layer | Arm length | Minimum planar distance to pins crossing that height |
|---|---:|---:|---:|
| O0 / 0 | 17.5 | 1.6801 | .15654 |
| O0 / 3 | 23.5 | 2.0850 | .14822 |
| O1 / 6 | 13.5 | 3.1667 | .11892 |
| O1 / 9 | 9.5 | 3.0632 | .11707 |
| O2 / 12 | 18.5 | 2.2211 | .14822 |
| O2 / 15 | 12.5 | 2.1910 | .12784 |

For example, the O1/rod-6 support-arm centerline is `(0,0) -> (.84,.04) -> (1.42,.10) -> (2,-.26) -> (3.06,-.26)` at layer 13.5. The O2/rod-12 arm is `(1,0) -> (1.38,.14) -> (1.96,-.28) -> (3.06,-.28)` at layer 18.5. All six explicit polylines are saved in `routed_support_rescue_0.040.json`; `routed_support_rescue.png` plots them against the relevant sampled moving-pin traces.

Using layer pitch .1, the following centerline distances were checked over the original 5,406 poses:

- Support arms to all moving pins in 3D: minimum .05000058.
- Short fixed bearing stubs to all moving pins: minimum .10000006.
- Exterior vertical posts to all moving straight rods: minimum .67904.
- Support arms to every rod plane, and stubs to every nonattached rod plane: vertical lower bound .05.

These exceed the .04 **combined centerline-clearance budget**. Actual thicknesses, radii, tolerances, bearing collars, and fastener heads would need to fit within that budget. Different support arms occupy distinct half-integer layers. Any intersections between stationary outer posts and stationary support arms can be joined as part of the same fixed frame.

This rescues the sampled geometric ground-support obstruction, not the overall prototype. At 50 mm pole spacing, .1 pitch is 5 mm, so the 26 rod planes span 125 mm vertically, the exterior frame rectangle is approximately 306 by 215 mm, and the support arms are approximately 84–158 mm long. Their stiffness, bearing bodies, moving pin/pin collisions, controlled-D1 support, friction, and simultaneous fabrication errors remain unchecked. Thin long printed cantilevers should not be presumed stiff enough. No detailed CAD or fabrication-ready design was produced.

## Input retention, hidden assemblies, friction

1. Memory is retained only while both input coordinates of D1 remain constrained at home. The released linkage has two degrees of freedom; it has no demonstrated energy barrier, passive latch, or autonomous unpowered stable memory. An XY actuator or a clamp is part of a practical test system.
2. The three initialized configurations are a closed operating subset, not a proof that the entire linkage has only three real assemblies. Extra inversor/pantograph assembly branches remain. Initialization, assembly procedure, and avoidance of those branches under wear/play are unresolved physical concerns.
3. Nonsingular equations do not establish manageable force, friction, backlash, or stiffness. The reference's sampled maximum memory-point velocity gain relative to D1 is 5.63, and its full-coordinate gain is 15.26. These are kinematic quantities, not measured actuator loads.
4. At 50 mm nominal pole spacing, the real mechanism sweeps about 265 × 174 mm, while each circular control part has radius 3.2 mm. The original all-box certificate at relative error 1e-5 corresponds to 0.5 micrometers on a 50 mm bar. The root's later 3e-5 bound corresponds to 1.5 micrometers. Those conservative proofs do not yet certify an ordinary loose-joint, printed physical prototype.

## Independent certificate audit

The root's `certify_rational_boxes.py` uses componentwise Taylor self-inclusion and a weighted contraction, with every elementary interval operation rounded outward by `numpy.nextafter`. Its bars are normalized by nominal length, so length uncertainty affects residuals but not the x-Jacobian. Ratio uncertainty appears both in the center residual and in the mixed `delta-alpha × delta-x` remainder. This covers 26 independent relative length errors and 4 independent relative ratio errors.

For each fixed parameter vector, each accepted cell has a unique root at every control value in its rectangle. At a shared control endpoint, the preceding and following root boxes lie in a larger convex box. Contraction on that larger box proves the two known endpoint roots equal. Self-inclusion of the larger gluing box is unnecessary. Start/end gluing to disjoint home boxes establishes the stated permutation on the initialized three states for the same fixed manufacturing vector.

No fatal defect in this reasoning or in the inspected directed-rounding implementation was found. Two implementation/provenance weaknesses were reported and the root subsequently corrected them: the home-disjointness assertion initially used ordinary floating arithmetic, and the manifest omitted hashes for two imported model dependencies.

`audit_certificate.py` independently rebuilds residual/Jacobian/remainder bounds using 70-digit Decimal floor/ceiling arithmetic. It checked the original **delta=1e-5** data: the 12 tightest inclusion cells, their preceding union boxes, all 3 home boxes, and all 12 start/end home gluings. All passed. The worst independently computed inclusion was `0.9997629165658667`, below the root's conservative binary64 bound `0.999762916612872`; maximum start/end gluing contraction was `0.2865017331`. Exact-dyadic home-box separation was also checked. The artifact stores source and cell-file hashes.

This is a complete source-level mathematical audit plus independent checks of selected difficult/connecting cells, not a second implementation replay of all 5,400 cells. The root's later **delta=3e-5** full certificate was not independently checked in this subtask. Neither certificate includes pivot-position error, collisions, compliance, friction, dynamics, or free-input stability.

## Research assessment

The existing work is substantial enough to rule out several tempting novelty claims:

- Bars and rotary joints implementing logic, memory, and reversible gates are already studied by [Merkle et al., Mechanical Computing Systems Using Only Links and Rotary Joints](https://arxiv.org/html/1801.03534).
- Algebraic maps and rich configuration spaces realized by planar linkages are already provided by [Kapovich–Millson](https://www.math.ucdavis.edu/~kapovich/EPR/KM_2002.pdf).
- Real loops permuting selected real nonsingular solutions, including kinematic assemblies, are within [Hauenstein–Regan's real monodromy structure](https://academicweb.nd.edu/~jhauenst/preprints/hrRealMonodromy.pdf). Tracking a closed initialized three-state subset does not escape that framework.
- Certified parameter-path tracking by Krawczyk is developed by [Duff–Lee 2024](https://arxiv.org/abs/2402.07053). Certified monodromy computation is directly addressed by [Duff–Lee 2026](https://arxiv.org/abs/2603.17288), with [a public implementation](https://github.com/klee669/CertifiedHomotopyTracking.jl). Extending a uniform interval containment argument to a static manufacturing box is not, by itself, a new theorem.
- Non-Abelian mechanical response/computation is also already an established direction; see [Guo et al.](https://arxiv.org/abs/2111.13933) and [Chen et al.](https://arxiv.org/abs/2502.16006). This mechanism should not be promoted as the first mechanical noncommutative memory.

A potentially meaningful question is whether one can **design and certify a manufacturable, finite-clearance, all-state reversible linkage with materially large simultaneous geometry and control-error margins**. To be a strong research theme rather than this one example, it would need a reusable synthesis/certification improvement and evidence across a meaningful design family, or a finished physical construction that demonstrates a previously unachieved combination of properties with a careful closest-prior comparison. Neither is established yet. Merely shrinking this 26-link design, changing pole placement, or applying a generic Krawczyk checker is insufficient novelty.

For the October 27 horizon, a rigorous numerical example and a transparent failure/feasibility study are plausible. A reliable layered physical prototype plus a strong general design result remains unproven. The present conclusion is **promising, reproducible initial phenomenon; research-theme acceptance still premature**.

## Commands

From the repository root, with its existing virtual environment:

```sh
OPENBLAS_NUM_THREADS=1 .venv/bin/python research-directions-20261002/round2-fresh/robustness/verify.py
OPENBLAS_NUM_THREADS=1 .venv/bin/python research-directions-20261002/round2-fresh/robustness/refine_validation.py
OPENBLAS_NUM_THREADS=1 .venv/bin/python research-directions-20261002/round2-fresh/robustness/heldout.py
OPENBLAS_NUM_THREADS=1 .venv/bin/python research-directions-20261002/round2-fresh/robustness/clearance_audit.py .04
OPENBLAS_NUM_THREADS=1 .venv/bin/python research-directions-20261002/round2-fresh/robustness/layer_audit.py .04
OPENBLAS_NUM_THREADS=1 .venv/bin/python research-directions-20261002/round2-fresh/robustness/support_layer_audit.py
OPENBLAS_NUM_THREADS=1 .venv/bin/python research-directions-20261002/round2-fresh/robustness/split_bearing_rescue.py
OPENBLAS_NUM_THREADS=1 .venv/bin/python research-directions-20261002/round2-fresh/robustness/routed_support_rescue.py
OPENBLAS_NUM_THREADS=1 .venv/bin/python research-directions-20261002/round2-fresh/robustness/audit_certificate.py
```

The validation scripts read their saved candidate-selection JSON files. The interval audit deliberately reads the original `rational_box_cells.json` data at delta=1e-5, not the later `rational_box_3e5_cells.json`.
