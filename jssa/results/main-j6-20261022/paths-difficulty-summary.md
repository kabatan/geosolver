# Path / stage / difficulty summary: jssa-main-j6-20261022
problems 323, runs 969
- runs where the algebraic prepass produced the candidates: 292/969 runs, 99 problems
- runs that went through numeric (NOMAD/SciPy) search: 584/969 runs, 197 problems
- runs where the hybrid second attempt triggered: 38/969 runs, 26 problems
- runs where rescue search triggered: 33/969 runs, 20 problems
- failed runs with no hard-feasible refined candidate: 2/969 runs, 2 problems
- failed runs that had hard-feasible candidates (lost in verification/identification): 14/969 runs, 9 problems
- zero-variable problems: 31
- wall-time share by stage (sum over runs): initial_probe 0.3%, search 18.9%, refinement 50.9%, exact_assembly 29.1%, rescue 0.8%

## Easy2Hard correlation (rating: higher = harder; C_i: mean over seeds of min(t,180) if exact match else 180)
- AIME: n=52, Spearman rho=0.561, 95% bootstrap CI [0.310, 0.758] (5000 resamples of problems)
  top-25% rating (>= 0.630): 13 problems; 3/3 exact with every run <=10s: 2/13 (15%); rest: 27/39 (69%)
- HMMT: n=79, Spearman rho=0.320, 95% bootstrap CI [0.096, 0.515] (5000 resamples of problems)
  top-25% rating (>= 0.844): 20 problems; 3/3 exact with every run <=10s: 8/20 (40%); rest: 43/59 (73%)

Notes: path flags are read from pipeline_summary (search.algebraic_branch_discovery, search.evaluation_count, search_staged_fallback.triggered, phase_rescue.triggered, refinement.hard_feasible_count). E2H rows include key-only matches (AIME final-integer, HMMT format-differs); no DSL-audit filtering applied yet.
