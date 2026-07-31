# Root-owned ordinary binding invocation

Run only after CPU14 is exclusively assigned.  Both commands are truth-blind;
they do not invoke the scorer or produce formal authority.

Frozen executable hashes before the root panel:

- connector: `d55a4170739defdd09111593741cbc2b7558d76b70414f53c30975695f8bf9e9`
- builder: `9b6ca3315316c59e573f77a96547e8b7ab41e7c18ed5ebfe94b1e95522a0eb82`
- aggregate runner: `d487b51a84775eb46aef950d3f9fea7dd3961f75e16238886b6388b716c07d4c`
- generated runner: `0092c07ec6aa6f88220ec216935d999277b48126ddb47972cb4ecf514cdc3399`
- generated result: `14baa1cf0a99b8a463e4c517c231ecd2983ad26c0bbc0eedacdca78244515faf`
- repaired projection census: `4028b556d53be1ce7adc3cc899347998d12ac490eea8dfc947187a9f8984f4aa`
- degree-one request manifest:
  `ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35`

Builder:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
taskset -c 14 \
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
/home/kabatan/work/solver-wt/target-constrained-nra-witness/research/experiments/EXP-V15-243-001/candidates/target_constrained_exact_nra_witness_v1/build_ordinary_binding_manifest.py \
  --degree1-requests /home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-requests.json \
  --degree1-requests-sha256 ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35 \
  --original-artifact-root /home/kabatan/work/solver-experiment-results/formal-control-development145-180-seed0/artifacts \
  --source-root /home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs \
  --proposal-root /home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1/ordinary-proposals \
  --manifest /home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1/requests.json \
  --expected-count 4 \
  --expected-cpu 14
```

After recording the builder's aggregate stdout and manifest SHA, run:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
taskset -c 14 \
/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
/home/kabatan/work/solver-wt/target-constrained-nra-witness/research/experiments/EXP-V15-243-001/candidates/target_constrained_exact_nra_witness_v1/run_ordinary_proposal_binding.py \
  --requests /home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1/requests.json \
  --requests-sha256 29f00d60bbdf4e4862eccdd3ac5c1274b48ba3ee5d4d0f5ee218cf42fea51233 \
  --source-root /home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs \
  --proposal-root /home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1/ordinary-proposals \
  --original-result-root /home/kabatan/work/solver-experiment-results/formal-control-development145-180-seed0/artifacts \
  --artifact-dir /home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1/connector-artifacts \
  --output /home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1/CONNECTOR-AGGREGATE.json \
  --expected-cpu 14 \
  --backend-timeout-seconds 3
```

The expected authority state is always false.  Promotion evidence consists
only of `ordinary_binding_pass_count`, `exact_replay_pass_count`, and
`readiness_count`; individual artifacts remain repository-external.
