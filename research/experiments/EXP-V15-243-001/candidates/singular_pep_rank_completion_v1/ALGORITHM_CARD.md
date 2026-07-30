# Singular PEP rank completion v1

## Hypothesis and mechanism

A safely extracted polynomial matrix may be structurally singular even though
its rank drops further at finitely many meaningful values.  Ordinary determinant
or companion enumeration refuses this state.  Five independent low-rank
polynomial completions can regularize it; true eigenvalues persist, while fake
completion eigenvalues vary and fail original-matrix rank-drop or left/right
completion-orthogonality checks.

The toy candidate:

1. estimates a stable normal rank from fixed source-independent probes;
2. rejects opaque, ambiguous and regular inputs to the unchanged baseline;
3. adds randomized corank-sized linear polynomial completions;
4. solves each small completed polynomial through a generalized companion
   linearization;
5. filters with original rank drop and both completion eigenvector overlaps;
6. requires agreement in at least four of five trials;
7. emits only real values passing untouched original polynomial-matrix replay.

The frozen ordinary regular-PEP baseline owns 12/16 slots and remains active on
regular inputs.  Rank completion owns only 4/16.  No case/family/truth/target,
known root, prior outcome or scorer signal reaches the mechanism.

## D0 and boundary

Single-process Python 3.12.11 / NumPy 2.5.1 / SciPy 1.18.0 D0: 12 cases, 7
families, `7 wins / 0 losses / 0 missing / 0 false / 0 extra`; positive signal
in singular pencils, singular quadratics and polynomially coupled/sheared
systems.  All 81 completion-created fake values were rejected.  Close roots,
complex-only roots, constant singular matrices, regular and opaque fallbacks
passed.  Eight metamorphic/safety tests passed.

This is proposal evidence, not a source compiler or exact certificate.  No real
solver connector, homotopy backend, common framework, scorer or formal corpus
run was created.  A future real seam may activate only for a mechanically safe
small polynomial matrix and must replay reconstructed configurations through
the canonical source/guard/branch verifier.

Primary basis: Hochstenbach, Mehl and Plestenjak,
[Numerical methods for eigenvalues of singular polynomial eigenvalue problems](https://arxiv.org/abs/2406.16832).
