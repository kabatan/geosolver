# Overlap and reopen audit

Disposition: **same VarPro lineage, admitted only through the archived analytic-derivative reopen gate**.

| Existing mechanism | State and update | Difference/reopen condition |
|---|---|---|
| `epoch_e_affine_fiber_varpro_g0` | Opaque evaluations; empirical affine directions from central-FD Jacobian differences; LS fibre then quotient GN | No operator/DAG affine proof and no exact projected derivative.  The candidate uses certified `A,dA,b,db` and never samples an FD Jacobian |
| `EXP-GEOCORE-002/solver_owned_variable_projection` | Exact overdetermined `A(x)y+c(x)`, pivoted-QR inner LS, but FD outer Jacobian | Direct predecessor.  Its measured failure was repeated inner solves at FD probes; its report explicitly names analytic/AD projected derivatives as the reopen gate satisfied here |
| `EXP-GEOCORE-002/reduced_space` | Square exact affine equation `A(x)y+b(x)=0`, one exact solution and implicit derivative for downstream residuals | It does not differentiate an overdetermined LS minimizer/pseudoinverse or retain the nonzero orthogonal fibre residual present away from a root |
| `structural_residual_tearing` / BTF | Maximum matching, SCC ordering, tear variables and progressive row activation | It changes causal solve order and later restores all rows; it neither solves a linear-variable LS optimum at every outer trial nor differentiates that optimum |
| `wave12_graph_schur_trust_step` | Schur elimination inside each pointwise linearized GN system | It eliminates a Jacobian block after linearization.  VarPro first solves the globally affine variables at the nonlinear trial, then linearizes the reduced residual |
| ordinary exact affine elimination | Static symbolic substitution through a square pivot equation | It rewrites/discharges once and cannot represent overdetermined LS fibres.  This candidate keeps every row and re-solves the numeric LS block at each trial |

Building a new affine detector, retuning condition thresholds, caching another
QR, or using an FD step size would be duplicate and is prohibited.  Real work
may reopen only if the existing DAG already supplies analytic affine
coefficients and derivatives with a sufficiently large block to repay the
remaining LS solve.
