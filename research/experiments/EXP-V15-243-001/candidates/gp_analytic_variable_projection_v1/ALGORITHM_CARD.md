# Analytic Golub--Pereyra variable projection v1

## Reopen hypothesis

The archived exact-DAG overdetermined VarPro arm repeatedly solved the inner
least-squares problem at every central-FD outer-Jacobian probe.  Its report
attributes 918 extra inner solves to this path and explicitly permits reopening
only for a general analytic/automatic projected derivative or substantially
larger separable blocks.

For an exactly certified operator/DAG block

`r(x,y) = A(x)y - b(x)`,

this candidate solves `y(x)=argmin_y ||r(x,y)||` at every accepted/trial `x`,
differentiates the normal equations analytically,

`dy = (A'A)^-1[dA'b + A'db - (dA'A + A'dA)y]`,

and runs the same reduced Gauss--Newton globalization as the FD control.  The
full original variables are reconstructed and the untouched residual/guard is
the only success authority.

The only causal delta is derivative formation:

- control: the same exact affine block, LS solve and reduced GN, but two
  projected inner solves per nonlinear coordinate for central FD;
- candidate: one LS solve plus the DAG-provided `A,dA,b,db` contraction.

Baseline owns 12/16 slots; analytic VarPro owns 4/16.  Rank-deficient or
ill-conditioned blocks, non-affine markers, opaque operators, nonfinite states
and replay failures fail closed.  No case/family/truth/target/outcome input is
visible.

## Toy D0

Single-process Python 3.12.11 / NumPy 2.5.1, CPU 8/9:

- 19 cases, 8 families; 14 positive cases in 4 separable families;
- recall `0 wins / 0 losses` versus the matched FD projected control;
- inner-solve work wins `14/14`, aggregate ratio `147/289 = 0.5087`;
- false/extra/crash `0`;
- rank-deficient, ill-conditioned, inconsistent, non-affine and opaque
  counters fail closed;
- analytic reduced Jacobian matches central FD; nonlinear-coordinate rotation,
  equation scaling, source replay and 75/25 immutability pass 8 tests.

This is a speed-work signal only, not real recall evidence.  The archived
epoch-e formal target-only aggregate remains `127/145`; no real/compiler/formal
run was performed here.

Primary basis: Golub and Pereyra,
[The Differentiation of Pseudo-Inverses and Nonlinear Least Squares Problems Whose Variables Separate](https://doi.org/10.1137/0710036),
and Español and Jeronimo,
[Convergence Analysis of a Variable Projection Method for Regularized Separable Nonlinear Inverse Problems](https://arxiv.org/abs/2402.08568).
