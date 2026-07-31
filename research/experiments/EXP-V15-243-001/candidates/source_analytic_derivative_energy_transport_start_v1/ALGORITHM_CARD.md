# SOURCE_ANALYTIC_DERIVATIVE_ENERGY_TRANSPORT_START_V1

- Hypothesis: exact polynomial source residuals can expose globally stiff
  rotated directions before search. A quarter of starts transported away from
  high derivative-energy directions can add basin diversity without sacrificing
  more than the fixed side-route quota.
- Mechanism: standardize finite source bounds; compute exact Gaussian moments
  of residual squares and gradient outer products; row-RMS normalize; form
  `C=sum E[grad(g_i) grad(g_i)^T]/E[g_i^2]`; use the formula-fixed
  `(C+trace(C)/n I)^(-1/2)` transport; renormalize to the original standardized
  radius.
- Routing state: source QQ polynomial AST and finite source bounds only. No
  target, answer, ID, family, truth, score, outcome, callback, rank, or progress.
- Portfolio/safety: three untouched baseline starts followed by one transported
  start. Bounds/guard rejection or any failure returns that exact baseline
  start. The route has no authority and never suppresses baseline search.
- D0: rotated positive, isotropic and opaque negatives, row-scale/variable
  permutation/affine-unit metamorphics, strict guard fallback, fixed 75/25
  quota, exact Gaussian moment and certificate-tamper tests.
- Static gate: at least 8 anonymous sources and 3 structural signatures within
  frozen degree/term/bit caps. Failure stops this candidate without tuning.
- Nearest archived candidates: QMC atlas, tropical scaling, Jacobian-nullspace,
  structural chart, Ruiz/local GN, moment SDP, and spectral-cosh. Those consume
  different state or use local/sample feedback rather than exact global source
  derivative moments.
- Research basis: Constantine, Dow, Wang, *SIAM J. Sci. Comput.* 36 (2014),
  DOI `10.1137/130916138`; Sobol and Kucherenko, *Math. Comput. Simulation* 79
  (2009), DOI `10.1016/j.matcom.2009.01.023`. The candidate's exact Gaussian
  polynomial moment realization is the experimental adaptation.
- Implementation quality: disposable candidate-local code. No framework,
  production connector, refactor, or shared platform work is authorized.
