# REAL_RADICAL_SOS_TARGET_IDENTITY_V1 — frozen aggregate real census

- Input: root-owned 85-record degree-one panel, SHA-256 `ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35`. Every resolved source must be a four-digit JSON file directly under the fixed `degree1-inputs` custody root; symlink/path escape and document ID/family/group/truth/outcome/result keys fail closed. Candidate sees only source path, finite endpoint, and primitive degree-one relation; it emits no individual path, hash, `q`, polynomial, witness, failure reason, or result. The pinned manifest plus fixed source root prevents use as an arbitrary source oracle.
- Compiler: directly load the existing target-constrained primitive cover and target-link adapter at pinned hashes. No compiler, semantic lowering, operator support, or resource threshold is added.
- Fixed certificate search: require a consistent QQ equality ideal and QQ raw target; require both `h∉I` and `h²∉I`; try `m=1,2` with all monomials of degree at most 3. First test the zero-free exact affine Gram solution, then an exact rational symmetric-diagonally-dominant Gram feasibility LP. Recover original-generator cofactors only through the already frozen degree 0–2 / 256-unknown witness search, and replay the final identity through `candidate.py`.
- Fixed budget: the existing degree-one adapter's 3.0-second record deadline; no threshold or parameter sweep. Timeout and every unsupported condition fail closed.
- Static join: only after identity replay, call the existing digest-pinned `typed_join.prepare_typed_regular_job`. This proves availability of the audited target-blind typed root/exact-replay compilation boundary, not root existence. Actual contained Krawczyk execution is a later root-owned, globally locked gate.
- Promotion gate: at least 4 identity-plus-typed-static intersections spanning at least 2 anonymous structural signatures. Authority and target release remain false regardless of counts.
- Output: stage counts, one joined anonymous signature count, gate, and fixed safety booleans only. Formal scorer, truth, holdout partitions, and individual outcomes are not read.

## Frozen result

- CPU14, Python 3.12.11 / SymPy 1.14.0; 3 synthetic/custody tests passed.
- Panel stages: input 85; primitive cover 33; safe QQ equality plus raw target 4; consistent non-unit ideal 4; direct `h` and `h²` miss 3; SOS search attempted 3; identity ready 0; typed-static intersection 0; joined signature count 0.
- Decision: **REAL_GATE_STOP**. This exact bounded mechanism does not proceed to the contained Krawczyk/existence worker gate. No bound, degree, timeout, Gram family, or compiler threshold was adjusted after seeing the aggregate.
- Safety: unexpected authority/release 0; authority and target release false; individual records absent. Repository-external aggregate SHA-256: `a591ad444f7b21e4c6f36450704d02b57dc2ac2a7b393a0b03ca81377b8497cf`.

Command after CPU14 is released:

`taskset -c 14 env PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python run_real_census.py --requests /home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-requests.json --output /home/kabatan/work/solver-experiment-results/real-radical-sos-target-identity-v1/REAL_CENSUS.json`
