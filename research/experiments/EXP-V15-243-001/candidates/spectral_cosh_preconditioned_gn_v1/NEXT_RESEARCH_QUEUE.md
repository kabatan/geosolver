# 2024–2026 primary-source diversification queue

Archive `rg` excluded already closed/repeated NewRUR, ordinary homotopy,
SVGD/DPP repulsion, Schwarz/FAS, extragradient, lazy-Gram LM, random-subspace,
and isolated-root Krawczyk mechanisms.

1. **Spectral cosh nonlinear-preconditioned GN** — state `r,J,J'r,H` and local
   spectrum; targets fast-growth GN contraction.  Baseline 75%, proposal route
   25%.  Nearest cubic/spectral LM only changes linear regularization.  Entry
   gate is a large model Newton coordinate plus a non-collinear transformed
   direction.  Generated D0 is under 30 minutes and passed.  Primary:
   https://arxiv.org/abs/2605.12666 .
2. **Exceptional-stratum projection with fiber products** — state source
   parameter, perturbation ball, replicated fibers, nearest discriminant point;
   targets solution-count/dimension flips near degeneracy.  Only unstable
   endpoint clusters get <=25%; coefficient monodromy keeps root orbits rather
   than data-space strata.  Gate is perturbation-stable reproduction of one
   exceptional stratum.  Full connector is not a 30-minute prototype.  Primary:
   https://arxiv.org/abs/2403.18749 .
3. **Local-monodromy orbit ledger** — state local witness fibers, loop
   permutations, orbit union-find, component dimension/degree; targets branches
   merged at a singular numeric root.  Only positive-nullity clusters get <=25%.
   Global coefficient monodromy has no local germ-orbit state.  Gate is stable
   multiple tangents plus a nonidentity local loop.  Toy D0 fits 30 minutes;
   production path connection does not.  Primary/official:
   https://arxiv.org/abs/2412.17952 and
   https://github.com/P-Edwards/LocalMonodromy.jl .
4. **Singular polynomial-eigenproblem rank completion** — state polynomial
   matrix, normal rank, random completions, left/right eigenvectors, true/fake
   cross-trial labels; targets structurally singular elimination pencils.  Safe
   polynomial inputs get <=25% and all eigenvalues replay canonically.  RUR and
   resultant routes do not keep randomized eigenstructure consensus.  Gate is
   stable normal-rank deficit plus trial-stable true roots.  Synthetic D0 fits
   30 minutes, source compiler does not.  Primary:
   https://arxiv.org/abs/2406.16832 .
5. **Moment-SOS atomic-support extraction** — state moment/localizing matrices,
   lower bound, flat ranks, atoms; targets missing real solutions in bounded
   low-degree polynomial systems.  Heavy route <=25%, baseline >=75%.  Existing
   local SDP/RUR routes lack a flat atomic measure certificate.  Gate is a zero
   bound and stable flat truncation whose atoms all replay.  Not a 30-minute
   connector.  Primary/official: https://arxiv.org/abs/2403.17241 and
   https://github.com/wangjie212/TSSOS .
6. **Noise-aware rank-deficient SQP rescue** — state measured residual/Jacobian
   noise, CPQR rank, normal/tangential steps, merit floor; targets redundant/noisy
   constraint stalls.  Plateau endpoints only get <=25%.  Elastic trust-funnel
   uses fixed tolerances rather than a measured noise floor.  Gate is stable rank
   deficit and a measured discrepancy that predicts the plateau.  Thin D0 fits
   30 minutes.  Primary: https://arxiv.org/abs/2503.06702 .
7. **Nonsquare generalized interval-Krawczyk surface patches** — state an
   `m<n` interval patch and inclusion certificate; targets positive-dimensional
   solution manifolds, unlike prior square isolated-root Krawczyk.  Small boxes
   only get <=25%.  Gate is an available interval extension, stable positive
   nullity, and successful generalized inclusion.  Not a 30-minute connector.
   Primary: https://arxiv.org/abs/2602.07718 .

