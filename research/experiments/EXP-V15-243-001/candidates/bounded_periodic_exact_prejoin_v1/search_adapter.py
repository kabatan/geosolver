"""Disposable 25% bounded/periodic prefix overlay for the current control.

The audited runtime candidate constructs the proposals.  This adapter retains
the original point at three of every four ordinals and uses only the audited
deterministic bounded/periodic cover at ``2 mod 4``.  It changes no residual,
local kernel, guard, endpoint replay, HP, or exact authority code.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from typing import Mapping

import numpy as np


RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_EXPERIMENT_RUNTIME",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
RUNTIME_CANDIDATE_ROOT = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/bounded_periodic_cover"
)
RUNTIME_ADAPTER = RUNTIME_CANDIDATE_ROOT / "adapter.py"
RUNTIME_CANDIDATE = RUNTIME_CANDIDATE_ROOT / "candidate.py"
EXPECTED_SHA256 = {
    RUNTIME_ADAPTER: "16b5d10c76a3660194c749ebbc8b97a44e52c382d5b65b9dbae9a88229c6eb08",
    RUNTIME_CANDIDATE: "9bef660e7a6ae1ea1600ccbfad69af52a4c69b2de2c61a5886e0abbcce47aee0",
}

CONTROL = "v15_frozen_start_stream"
ARM = "bounded_periodic_exact_prejoin_25pct_v1"
ARMS = (CONTROL, ARM)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


for _path, _expected in EXPECTED_SHA256.items():
    if not _path.is_file() or _sha256(_path) != _expected:
        raise RuntimeError(f"bounded/periodic repaired dependency changed: {_path}")

RUNTIME = _load("geotarget_prejoin_bounded_runtime_adapter", RUNTIME_ADAPTER)
CANDIDATE = RUNTIME.CANDIDATE
PRECISION_RUNTIME = RUNTIME.PRECISION_RUNTIME


def build_literal_prefix(document, base_case, base_policy):
    return RUNTIME.build_literal_prefix(document, base_case, base_policy)


def compile_program(arm: str, document):
    if arm not in ARMS:
        raise ValueError(f"unknown arm: {arm!r}")
    return RUNTIME.compile_program(RUNTIME.CONTROL, document)


def _quarter_prefix(program, literal_prefix):
    proposed = CANDIDATE.emit_prefix(
        program.document,
        literal_prefix,
        seed=RUNTIME._proposal_seed(literal_prefix),
        wave=RUNTIME.WAVE1,
    )
    if proposed is literal_prefix:
        return literal_prefix, {
            "eligible": False,
            "side_route_launches": 0,
            "baseline_launches": len(tuple(literal_prefix.points)),
        }

    original_points = tuple(literal_prefix.points)
    original_sources = tuple(literal_prefix.sources)
    output = []
    sources = []
    side_route_launches = 0
    for ordinal, (original, replacement) in enumerate(
        zip(original_points, proposed.points, strict=True)
    ):
        if ordinal % 4 == 2:
            output.append(np.asarray(replacement, dtype=float).copy())
            sources.append(proposed.sources[ordinal])
            side_route_launches += 1
        else:
            output.append(np.asarray(original, dtype=float).copy())
            sources.append(original_sources[ordinal])
            if output[-1].tobytes() != np.asarray(original, dtype=float).tobytes():
                raise AssertionError("75% baseline ordinal changed")

    activation = dict(proposed.activation)
    activation.update(
        {
            "wave": ARM,
            "side_route_launches": side_route_launches,
            "baseline_launches": len(output) - side_route_launches,
            "side_route_fraction_upper_bound": 0.25,
            "baseline_fraction_lower_bound": 0.75,
            "sobol_launches": 0,
            "antithetic_sobol_launches": 0,
            "deterministic_cover_launches": side_route_launches,
            "literal_passthrough_launches": len(output) - side_route_launches,
        }
    )
    frozen = tuple(output)
    return CANDIDATE.ProposalPrefix(
        points=frozen,
        sources=tuple(sources),
        scale_exponents=tuple(literal_prefix.scale_exponents),
        literal_scales=np.asarray(literal_prefix.literal_scales, dtype=float).copy(),
        plan=proposed.plan,
        sha256=CANDIDATE._prefix_digest(frozen, sources),
        activation=activation,
    ), activation


def run_local_arm(
    arm: str,
    *,
    base_case,
    budget,
    program,
    literal_prefix,
    callback_cap: int,
    callbacks_per_start: int,
    deadline_monotonic: float,
):
    if arm not in ARMS:
        raise ValueError(f"unknown arm: {arm!r}")
    effective = literal_prefix
    activation: Mapping[str, object] = {
        "eligible": False,
        "side_route_launches": 0,
        "baseline_launches": len(tuple(literal_prefix.points)),
    }
    status = "control"
    if arm == ARM:
        effective, activation = _quarter_prefix(program, literal_prefix)
        status = "eligible" if effective is not literal_prefix else "inapplicable_passthrough"

    outcome = RUNTIME.V15.run_local_arm(
        RUNTIME.V15.CANDIDATE,
        base_case=base_case,
        budget=budget,
        program=program.local_program,
        literal_prefix=effective,
        callback_cap=callback_cap,
        callbacks_per_start=callbacks_per_start,
        deadline_monotonic=deadline_monotonic,
    )
    counters = Counter(outcome.counters)
    counters[f"bounded_periodic_prejoin_status:{status}"] += 1
    for name in ("side_route_launches", "baseline_launches"):
        counters[f"bounded_periodic_prejoin_{name}"] += int(activation.get(name, 0))
    return replace(outcome, counters=dict(counters))


def configuration_manifest() -> Mapping[str, object]:
    return {
        "schema_version": "geotarget.bounded-periodic-exact-prejoin/v1",
        "arms": list(ARMS),
        "side_route_fraction_upper_bound": 0.25,
        "baseline_fraction_lower_bound": 0.75,
        "side_route_ordinal": "2 mod 4 audited deterministic cover",
        "other_ordinals_same_control_bytes": True,
        "source_authority": "finite explicit intersection or whole-AST proved period",
        "local_solver_or_authority_modified": False,
        "truth_case_family_target_count_outcome_routing": False,
        "runtime_dependency_sha256": {
            str(path): digest for path, digest in EXPECTED_SHA256.items()
        },
    }


BINDING_RECORD = configuration_manifest()
