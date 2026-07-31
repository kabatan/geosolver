# LOCAL_PRECONDITIONED_PM — aggregate-only real readiness census

- Input custody: root-owned 85 degree-1 requests. Runner emits no individual path, source/case hash, record, failure reason, or case result.
- Frozen stages: runtime build; exact symbolic compile; QQ polynomial n≤3/degree≤6; full canonical guard/branch/definedness obligation compile; truth-blind square active subset with omitted exact consequences; degree-1 target identity; one rounded rational endpoint preconditioner and local box; exact PM faces; canonical replay; strict full-box target-range isolator.
- Fixed resources: CPU 14, one process, 3 seconds per record, endpoint denominator 4096, preconditioner denominator 65536, radius `1/64 + 2|AF(endpoint)|`, face coefficient height≤4096, no subdivision. No parameter was adjusted after seeing the census.
- Runtime provenance: commit `51c7f8d79815e0c29f07b51a26a7b553adcac24a`; 556 decision-bearing Python files; pre/post aggregate SHA `7d5d4fc193dc5d53fbd9014aa2e1fc9e08ae11771912ee863a035c32c7a6dec4`; unchanged=true.
- Aggregate: input 85; runtime built 85; symbolic compiled 29; typed polynomial 0; all later proof stages 0; ready 0; anonymous signatures 0.
- Decision: **REAL_GATE_STOP** because the fixed gate requires ready≥4 and anonymous signatures≥2. This is applicability evidence only; it grants no authority or release claim.

Root invocation:

`taskset -c 14 env PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=<geotarget-src> <python> run_real_census.py --manifest <degree1-requests.json> --runtime-root <runtime-root>`
