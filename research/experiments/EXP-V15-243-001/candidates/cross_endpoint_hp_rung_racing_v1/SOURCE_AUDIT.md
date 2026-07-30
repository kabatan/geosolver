# Cross-endpoint HP rung feasibility audit

Verdict: `HOLD_NO_RESUMABLE_HP_STATE`.

The frozen exact outer calls one ordinary HP attempt and then launches one fresh exact-coordinate child for that endpoint. The child creates a temporary trial, invokes the frozen refiner once, and consumes only its final proposal document. The refiner constructs all `155/232/320 dps` lanes inside one process, performs PSLQ and polynomial metadata construction only after all lanes complete, and exposes no checkpoint, resume, rung, partial-lane, or warm-state CLI/artifact.

Consequently, a true low-rung handoff would require splitting and serializing legacy evaluator/refiner state, changing the frozen child contract, and teaching later invocations to restore mpmath/solver state. This is not a minimal candidate hook and exceeded the 30-minute non-algorithm limit. Restarting the child from scratch and ranking final telemetry would reproduce the already-frozen cross-endpoint HP VOI/species scheduler rather than reuse work.

The repository wrapper `champion_v2_poc_cross_endpoint_hp_preloaded.py` references `candidates/cross_endpoint_hp_rungs`, but that module is absent from the current frozen source closure. Prior commit `b75145de` already generated-tested censor-aware cross-endpoint HP VOI. Prior audit `24a2c9a7` stopped the exact-species composition as duplicate unless a hash-bound resumable proof fragment avoids recomputing its prefix. That reopen gate is not satisfied.

No solver worker is emitted. The only fallback artifact is a broad, source-only exact-descriptor-species eligibility scanner. It groups endpoints only by exact source SHA, requires at least two source-safe endpoints at runtime, gives every endpoint a low rung, shares neither descriptors nor authority, and still requires endpoint-local canonical replay. It is an eligibility signal, not an authority or scheduling implementation.
