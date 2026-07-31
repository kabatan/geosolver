# Source-ideal signed automorphism orbit starts

`SOURCE_IDEAL_SIGNED_AUTOMORPHISM_ORBIT_START_V1` is a disposable,
truth-blind proposal lane.  It finds exact signed coordinate permutations that
preserve a small rational polynomial source cover, then maps one already-safe
endpoint through the generated finite orbit.  Every mapped point is returned
only after untouched canonical source replay.

This is not coefficient monodromy.  It has no coefficient loop, discriminant,
path tracker, Newton correction, root cover, continuation parameter, or target
descriptor.  Equality preservation is deliberately narrower than ideal
automorphism: the QQ row space of the supplied residual polynomials must be
exactly invariant.  Ordered predicates and source bounds must also be exactly
invariant.  This makes rejection common but avoids a heuristic ideal-membership
claim.

## Commands (benchmark owner only)

All Python execution is pinned to CPU14.  Candidate owners do not inspect
individual records from the real panel.

```bash
taskset -c 14 /home/kabatan/work/solver/.venv/bin/python \
  research/experiments/EXP-SOURCE-IDEAL-AUTOMORPHISM-001/run_generated_d0.py

taskset -c 14 /home/kabatan/work/solver/.venv/bin/python -m pytest -q \
  research/experiments/EXP-SOURCE-IDEAL-AUTOMORPHISM-001/test_candidate.py

taskset -c 14 /home/kabatan/work/solver/.venv/bin/python \
  research/experiments/EXP-SOURCE-IDEAL-AUTOMORPHISM-001/run_truth_blind_activation.py \
  --requests /home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-requests.json \
  --requests-sha256 ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35 \
  --expected-cpu 14 \
  --output /home/kabatan/work/solver-experiment-results/source-ideal-signed-automorphism-orbit-v1/aggregate.json
```

The real gate is `activation_source_count >= 3`,
`anonymous_signature_count >= 2`, and zero false emission, source-invalid, or
fallback-byte mismatch.  Its aggregate contains no source path, endpoint,
coefficient, proposal, target, signature, or per-case failure.

Final disposition: generated D0 passed, but the frozen anonymous panel had
zero structural activation.  The candidate is stopped without retuning; see
`REAL_ACTIVATION_AGGREGATE.json` and `ALGORITHM_CARD.md`.
