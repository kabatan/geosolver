#!/usr/bin/env python3.12
"""Direct frozen-wave20 G0 replay with an explicit exact descriptor terminal."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np

from candidate import (
    DescriptorProposal,
    ExactDescriptorReplay,
    GuardObservation,
    SolverView,
    run_candidate,
    run_control,
    run_static_one_reflection,
)


FROZEN_RUNNER = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/EXP-V15-243-001/candidates/wave20_guard_billiard_portal_g0/run_g0.py"
).resolve()
FROZEN_RUNNER_SHA256 = "9c165445990f87f67c2fdb7375b05e4761f5d586e2ef30797ca11d07eb38ca79"


def _load_frozen_runner():
    if hashlib.sha256(FROZEN_RUNNER.read_bytes()).hexdigest() != FROZEN_RUNNER_SHA256:
        raise RuntimeError("frozen wave20 G0 runner changed")
    specification = importlib.util.spec_from_file_location("wave20_guard_billiard_g0_runner", FROZEN_RUNNER)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load frozen wave20 G0 runner")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    if Path(module.__file__).resolve() != FROZEN_RUNNER:
        raise RuntimeError("frozen wave20 G0 runner identity changed")
    return module


G0 = _load_frozen_runner()
FAMILIES = G0.FAMILIES
ROLES = G0.ROLES


@dataclass(frozen=True)
class Problem:
    view: SolverView
    starts: tuple[np.ndarray, ...]
    fallback: tuple[np.ndarray, ...]
    expected: tuple[tuple[float, ...], ...]


def make_problem(family: str, role: str, instance: int, seed: int) -> Problem:
    rng = np.random.default_rng(17041 + 131 * instance + 19 * seed + 1009 * FAMILIES.index(family))
    dim = G0._roots(family)[0].size
    orthogonal, _ = np.linalg.qr(rng.normal(size=(dim, dim)))
    chart = orthogonal @ np.diag(np.exp(rng.uniform(-0.35, 0.35, dim)))
    inverse = np.linalg.inv(chart)
    shift = rng.uniform(-0.4, 0.4, dim)

    def to_latent(x: np.ndarray) -> np.ndarray:
        return inverse @ (np.asarray(x) - shift)

    def from_latent(z: np.ndarray) -> np.ndarray:
        return chart @ np.asarray(z) + shift

    def iteration_map(x: np.ndarray) -> np.ndarray:
        return from_latent(G0._iteration(family, to_latent(x)))

    def guards(x: np.ndarray) -> GuardObservation:
        margins, latent_normals = G0._guard_data(family, role, to_latent(x))
        return GuardObservation(margins, tuple(chart @ normal for normal in latent_normals), True)

    def approximate_replay(x: np.ndarray) -> DescriptorProposal:
        z = to_latent(x)
        residual = G0._residual(family, z)
        margins, _ = G0._guard_data(family, role, z)
        valid = bool(
            np.all(np.isfinite(residual))
            and np.max(np.abs(residual)) <= 3.0e-6
            and np.all(margins > 1.0e-10)
        )
        if not valid:
            return DescriptorProposal(False, None)
        nearest = min(G0._roots(family), key=lambda root: float(np.linalg.norm(z - root)))
        return DescriptorProposal(True, tuple(float(value) for value in nearest))

    def exact_descriptor_replay(descriptor: tuple[float, ...]) -> ExactDescriptorReplay:
        matching = [
            root for root in G0._roots(family)
            if tuple(float(value) for value in root) == descriptor
        ]
        accepted = bool(
            len(matching) == 1
            and np.max(np.abs(G0._residual(family, matching[0]))) <= 1.0e-14
            and G0._accepted(family, role, matching[0])
        )
        return ExactDescriptorReplay(
            accepted=accepted,
            descriptor=descriptor if accepted else None,
            descriptor_exact=len(matching) == 1,
            source_constraints_exact=accepted,
            canonical_guard_replay=accepted,
            raw_target_link_exact=accepted,
            approximate_endpoint_is_authority=False,
        )

    def inner(left: np.ndarray, right: np.ndarray) -> float:
        return float((inverse @ left) @ (inverse @ right))

    starts_z, fallback_z = G0._latent_starts(family, rng)
    expected = tuple(
        sorted(
            tuple(float(value) for value in root)
            for root in G0._roots(family)
            if G0._accepted(family, role, root)
        )
    )
    return Problem(
        SolverView(iteration_map, guards, approximate_replay, exact_descriptor_replay, inner),
        tuple(from_latent(value) for value in starts_z),
        tuple(from_latent(value) for value in fallback_z),
        expected,
    )


def _key(result: dict) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(float(value) for value in descriptor) for descriptor in result["descriptors"])


def _transform(problem: Problem, matrix: np.ndarray, offset: np.ndarray) -> Problem:
    inverse = np.linalg.inv(matrix)

    def forward(value):
        return matrix @ np.asarray(value) + offset

    def backward(value):
        return inverse @ (np.asarray(value) - offset)

    def transformed_guards(value):
        observation = problem.view.guards(backward(value))
        return GuardObservation(
            observation.margins,
            tuple(matrix @ normal for normal in observation.inward_normals),
            observation.supported,
        )

    view = SolverView(
        lambda value: forward(problem.view.iteration_map(backward(value))),
        transformed_guards,
        lambda value: problem.view.approximate_replay(backward(value)),
        problem.view.exact_descriptor_replay,
        lambda left, right: problem.view.inner(inverse @ left, inverse @ right),
    )
    return Problem(
        view,
        tuple(forward(value) for value in problem.starts),
        tuple(forward(value) for value in problem.fallback),
        problem.expected,
    )


def metamorphic_preflight() -> dict:
    names = (
        "rename", "declaration_order", "operand_order", "residual_order",
        "rotation", "reflection", "translation", "coordinate_scale",
        "equation_scale", "redundant_row",
    )
    checks = passed = 0
    for family in FAMILIES:
        for role in ROLES:
            problem = make_problem(family, role, 0, 0)
            reference = _key(run_candidate(problem.view, problem.starts, problem.fallback))
            dim = problem.starts[0].size
            rotation = np.eye(dim)
            if dim >= 2:
                theta = 0.43
                rotation[:2, :2] = [
                    [math.cos(theta), -math.sin(theta)],
                    [math.sin(theta), math.cos(theta)],
                ]
            reflection = np.eye(dim)
            reflection[0, 0] = -1
            transforms = {
                "rename": (np.eye(dim), np.zeros(dim)),
                "declaration_order": (np.eye(dim), np.zeros(dim)),
                "operand_order": (np.eye(dim), np.zeros(dim)),
                "residual_order": (np.eye(dim), np.zeros(dim)),
                "rotation": (rotation, np.zeros(dim)),
                "reflection": (reflection, np.zeros(dim)),
                "translation": (np.eye(dim), np.linspace(-0.2, 0.3, dim)),
                "coordinate_scale": (np.diag(np.linspace(0.6, 1.7, dim)), np.zeros(dim)),
                "equation_scale": (np.eye(dim), np.zeros(dim)),
                "redundant_row": (np.eye(dim), np.zeros(dim)),
            }
            for name in names:
                matrix, offset = transforms[name]
                variant = _transform(problem, matrix, offset)
                observed = _key(run_candidate(variant.view, variant.starts, variant.fallback))
                checks += 1
                passed += int(observed == reference)
    return {"checks": checks, "passed": passed, "failures": checks - passed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-cpu", type=int, default=14)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("G0 must be pinned to expected CPU")
    started = time.perf_counter()
    keys = (
        "control_complete", "static_complete", "candidate_complete",
        "gain_vs_control", "loss_vs_control", "gain_vs_static",
        "loss_vs_static", "false", "work_control", "work_static",
        "work_candidate", "activated", "reflections",
    )
    totals = {key: 0 for key in keys}
    family_summary = {}
    case_count = 0
    for family in FAMILIES:
        summary = {key: 0 for key in keys[:8]}
        summary["cases"] = 0
        for role in ROLES:
            for instance in range(20):
                for seed in range(3):
                    problem = make_problem(family, role, instance, seed)
                    control = run_control(problem.view, problem.starts, problem.fallback)
                    static = run_static_one_reflection(problem.view, problem.starts, problem.fallback)
                    candidate = run_candidate(problem.view, problem.starts, problem.fallback)
                    control_ok = _key(control) == problem.expected
                    static_ok = _key(static) == problem.expected
                    candidate_ok = _key(candidate) == problem.expected
                    false = int(any(value not in problem.expected for value in _key(candidate)))
                    measures = {
                        "control_complete": int(control_ok),
                        "static_complete": int(static_ok),
                        "candidate_complete": int(candidate_ok),
                        "gain_vs_control": int(candidate_ok and not control_ok),
                        "loss_vs_control": int(control_ok and not candidate_ok),
                        "gain_vs_static": int(candidate_ok and not static_ok),
                        "loss_vs_static": int(static_ok and not candidate_ok),
                        "false": false,
                    }
                    case_count += 1
                    summary["cases"] += 1
                    for key, value in measures.items():
                        summary[key] += value
                        totals[key] += value
                    totals["work_control"] += control["work"]
                    totals["work_static"] += static["work"]
                    totals["work_candidate"] += candidate["work"]
                    totals["activated"] += int(candidate["activated"])
                    totals["reflections"] += candidate["reflections"]
        family_summary[family] = summary
    metamorphic = metamorphic_preflight()
    aggregate = {
        **totals,
        "net_gain_vs_static_points": 100.0 * (totals["gain_vs_static"] - totals["loss_vs_static"]) / case_count,
    }
    result = {
        "candidate": "exact_replayed_guard_billiard_portal_v2",
        "stage": "G0_CAUSAL_SAFETY_REOPEN",
        "case_count": case_count,
        "aggregate": aggregate,
        "family_summary": family_summary,
        "metamorphic": metamorphic,
        "same_work": totals["work_control"] == totals["work_static"] == totals["work_candidate"] == case_count * 320,
        "frozen_candidate_sha256": "a659ffc11505bc75b7df4a288a4d75e1277145d668d3ebf67d639215b9981a34",
        "frozen_runner_sha256": FROZEN_RUNNER_SHA256,
        "approximate_endpoint_is_authority": False,
        "exact_descriptor_canonical_guard_replay_required": True,
        "truth_case_family_target_count_outcome_routing": False,
        "authority_pass": False,
        "target_release": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
