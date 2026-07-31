# REAL_RADICAL_SOS_TARGET_IDENTITY_V1 — frozen aggregate real census

- Input: root-owned 85-record degree-one panel, SHA-256 `ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35`. Candidate sees only source path, finite endpoint, and primitive degree-one relation; it emits no individual path, hash, `q`, polynomial, witness, failure reason, or result.
- Compiler: directly load the existing target-constrained primitive cover and target-link adapter at pinned hashes. No compiler, semantic lowering, operator support, or resource threshold is added.
- Fixed certificate search: require a consistent QQ equality ideal and QQ raw target; require both `h∉I` and `h²∉I`; try `m=1,2` with all monomials of degree at most 3. First test the zero-free exact affine Gram solution, then an exact rational symmetric-diagonally-dominant Gram feasibility LP. Recover original-generator cofactors only through the already frozen degree 0–2 / 256-unknown witness search, and replay the final identity through `candidate.py`.
- Fixed budget: the existing degree-one adapter's 3.0-second record deadline; no threshold or parameter sweep. Timeout and every unsupported condition fail closed.
- Static join: only after identity replay, call the existing digest-pinned `typed_join.prepare_typed_regular_job`. This proves availability of the audited target-blind typed root/exact-replay compilation boundary, not root existence. Actual contained Krawczyk execution is a later root-owned, globally locked gate.
- Promotion gate: at least 4 identity-plus-typed-static intersections spanning at least 2 anonymous structural signatures. Authority and target release remain false regardless of counts.
- Output: stage counts, one joined anonymous signature count, gate, and fixed safety booleans only. Formal scorer, truth, holdout partitions, and individual outcomes are not read.

Command after CPU14 is released:

`taskset -c 14 env PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python run_real_census.py --requests /home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-requests.json --output /home/kabatan/work/solver-experiment-results/real-radical-sos-target-identity-v1/REAL_CENSUS.json`
