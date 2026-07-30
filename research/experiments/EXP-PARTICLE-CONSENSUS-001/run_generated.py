"""Generated D0 for equality-forced few-particle consensus."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from candidate import NumericalProblem, replay_valid, solve_portfolio


Array = np.ndarray


@dataclass(frozen=True)
class Fixture:
    family: str  # harness-only; never copied into NumericalProblem
    category: str
    problem: NumericalProblem
    truth: tuple[Array, ...]
    base_seed: int
    transform_variant: int


def _analytic_families(seed: int) -> list[tuple[str, callable, callable, Array, tuple[Array, ...]]]:
    rng = np.random.default_rng(seed)
    a = 0.72 + 0.08 * rng.random()
    r = 1.15 + 0.08 * rng.random()
    c = 0.18 + 0.05 * rng.random()
    q = 0.58 + 0.08 * rng.random()

    def parabola(x: Array) -> Array:
        return np.array([x[1] - x[0] ** 2, x[0] ** 2 - a**2])

    def j_parabola(x: Array) -> Array:
        return np.array([[-2 * x[0], 1.0], [2 * x[0], 0.0]])

    y = a * a
    roots_p = (np.array([-a, y]), np.array([a, y]))

    def circle(x: Array) -> Array:
        return np.array([x[0] ** 2 + x[1] ** 2 - r**2, x[1] - c])

    def j_circle(x: Array) -> Array:
        return np.array([[2 * x[0], 2 * x[1]], [0.0, 1.0]])

    xr = np.sqrt(r * r - c * c)
    roots_c = (np.array([-xr, c]), np.array([xr, c]))

    def disconnected(x: Array) -> Array:
        return np.array([(x[0] + 1.1) * (x[0] - 0.25) * (x[0] - 1.35), x[1] - q * x[0]])

    def j_disconnected(x: Array) -> Array:
        u = x[0]
        derivative = (u - 0.25) * (u - 1.35) + (u + 1.1) * (u - 1.35) + (u + 1.1) * (u - 0.25)
        return np.array([[derivative, 0.0], [-q, 1.0]])

    roots_d = tuple(np.array([u, q * u]) for u in (-1.1, 0.25, 1.35))

    def inconsistent(x: Array) -> Array:
        radius = x[0] ** 2 + x[1] ** 2
        return np.array([radius - 1.0, radius - 1.09])

    def j_inconsistent(x: Array) -> Array:
        return np.array([[2 * x[0], 2 * x[1]], [2 * x[0], 2 * x[1]]])

    return [
        ("curved_parabola_intersection", parabola, j_parabola, np.array([0.82, 0.45]), roots_p),
        ("curved_circle_slice", circle, j_circle, np.array([1.0, 0.4]), roots_c),
        ("three_disconnected_roots", disconnected, j_disconnected, np.array([1.1, 0.65]), roots_d),
        ("inconsistent_concentric_equalities", inconsistent, j_inconsistent, np.array([0.8, 0.45]), ()),
    ]


def _opaque_families(seed: int) -> list[tuple[str, callable, Array, tuple[Array, ...]]]:
    delta = 0.03 * (seed % 3)

    def abs_corner(x: Array) -> Array:
        return np.array([abs(x[0]) - (0.75 + delta), x[1] - 0.2])

    roots_a = (np.array([-(0.75 + delta), 0.2]), np.array([0.75 + delta, 0.2]))

    def branch(x: Array) -> Array:
        first = x[0] - 0.6 if x[0] >= 0 else -x[0] - 0.6
        return np.array([first, x[1] + 0.15])

    roots_b = (np.array([-0.6, -0.15]), np.array([0.6, -0.15]))

    def inconsistent(x: Array) -> Array:
        return np.array([abs(x[0]) - 0.5, abs(x[0]) - 0.6, x[1]])

    return [
        ("opaque_absolute_corner", abs_corner, np.array([0.8, 0.25]), roots_a),
        ("opaque_piecewise_branch", branch, np.array([0.7, -0.1]), roots_b),
        ("opaque_inconsistent_fallback", inconsistent, np.array([0.55, 0.1]), ()),
    ]


def _transform(
    family: str,
    residual,
    jacobian,
    start: Array,
    truth: tuple[Array, ...],
    variant: int,
    *,
    smooth: bool,
    base_seed: int,
) -> Fixture:
    # base_x = A @ transformed_x + shift; all signals are anonymous numeric data.
    if variant == 0:
        a = np.eye(2)
        shift = np.zeros(2)
        row = np.eye(2) if smooth else None
    elif variant == 1:
        a = np.array([[0.0, -2.0], [0.5, 0.0]])
        shift = np.array([0.2, -0.1])
        row = np.array([[0.0, -4.0], [0.25, 0.0]]) if smooth else None
    elif variant == 2:
        a = np.array([[-0.5, 0.0], [0.0, 2.0]])
        shift = np.array([-0.15, 0.25])
        row = np.array([[-2.0, 0.0], [0.0, 8.0]]) if smooth else None
    else:
        a = np.array([[0.0, 0.5], [2.0, 0.0]])
        shift = np.array([0.1, 0.15])
        row = np.array([[0.0, 2.0], [-0.5, 0.0]]) if smooth else None
    inverse = np.linalg.inv(a)

    def transformed_residual(z: Array) -> Array:
        value = residual(a @ z + shift)
        return row @ value if row is not None else value

    if jacobian is not None:
        def transformed_jacobian(z: Array) -> Array:
            return row @ jacobian(a @ z + shift) @ a
    else:
        transformed_jacobian = None

    transformed_start = inverse @ (start - shift)
    transformed_truth = tuple(inverse @ (root - shift) for root in truth)
    # A is signed permutation times diagonal, so these are exact chart units.
    chart_scale = 1.0 / np.linalg.norm(a, axis=0)
    problem = NumericalProblem(
        residual=transformed_residual,
        jacobian=transformed_jacobian,
        start=transformed_start,
        chart_scale=chart_scale,
        smooth_numeric_jacobian=smooth,
    )
    category = "positive" if truth else "negative"
    return Fixture(family, category, problem, transformed_truth, base_seed, variant)


def fixtures(seeds: range = range(10)) -> list[Fixture]:
    result: list[Fixture] = []
    for seed in seeds:
        for family, residual, jacobian, start, truth in _analytic_families(seed):
            for variant in range(4):
                result.append(_transform(family, residual, jacobian, start, truth, variant, smooth=True, base_seed=seed))
        for family, residual, start, truth in _opaque_families(seed):
            # Opaque fallback checks permutation through output-set parity; equation
            # scaling cannot be exposed without a differentiable row capability.
            for variant in (0,):
                result.append(_transform(family, residual, None, start, truth, variant, smooth=False, base_seed=seed))
    return result


def _matched(found: list[Array], truth: tuple[Array, ...], scale: Array) -> set[int]:
    matched: set[int] = set()
    for point in found:
        distances = [np.linalg.norm((point - root) / scale, ord=np.inf) for root in truth]
        if distances and min(distances) <= 2e-5:
            matched.add(int(np.argmin(distances)))
    return matched


def run() -> dict:
    records = []
    summary: dict[str, dict[str, int]] = {}
    callback_parity = True
    safety_violations = 0
    metamorphic_groups: dict[tuple[str, int], list[tuple[int, int]]] = {}
    for ordinal, fixture in enumerate(fixtures()):
        arms = {}
        for arm in ("control", "candidate"):
            raw = solve_portfolio(fixture.problem, arm)
            found = replay_valid(fixture.problem, raw.proposals)
            matched = _matched(found, fixture.truth, fixture.problem.chart_scale)
            false = len(found) - len(matched)
            safety_violations += false
            arms[arm] = (raw, found, matched, false)
            fam = summary.setdefault(fixture.family, {"control": 0, "candidate": 0, "gain": 0, "loss": 0, "false": 0})
            fam[arm] += len(matched)
            fam["false"] += false
        callback_parity &= arms["control"][0].callbacks == arms["candidate"][0].callbacks == 512
        control_set, candidate_set = arms["control"][2], arms["candidate"][2]
        gain = len(candidate_set - control_set)
        loss = len(control_set - candidate_set)
        summary[fixture.family]["gain"] += gain
        summary[fixture.family]["loss"] += loss
        key = (fixture.family, fixture.base_seed)
        metamorphic_groups.setdefault(key, []).append((len(control_set), len(candidate_set)))
        records.append({
            "family": fixture.family,
            "category": fixture.category,
            "variant": fixture.transform_variant,
            "control_exact_roots": len(control_set),
            "candidate_exact_roots": len(candidate_set),
            "gain": gain,
            "loss": loss,
            "false": arms["candidate"][3],
            "callbacks": arms["candidate"][0].callbacks,
            "baseline_fraction": arms["candidate"][0].activation["baseline_quota_fraction"],
            "candidate_mode": arms["candidate"][0].activation["mode"],
            "force_events": arms["candidate"][0].activation.get("equality_force_motion_events", 0),
        })

    # Every four-variant analytic group must preserve paired root counts.
    metamorphic_pass = True
    for values in metamorphic_groups.values():
        if len(values) == 4:
            metamorphic_pass &= len(set(values)) == 1
    aggregate = {
        "schema": "geotarget.exp-particle-consensus-001.d0/v1",
        "fixture_count": len(records),
        "arm_runs": 2 * len(records),
        "callback_parity_512": callback_parity,
        "baseline_quota_min": min(record["baseline_fraction"] for record in records),
        "safety_false_extra": safety_violations,
        "metamorphic_group_count": sum(len(v) == 4 for v in metamorphic_groups.values()),
        "metamorphic_pass": metamorphic_pass,
        "totals": {
            "control_exact_roots": sum(r["control_exact_roots"] for r in records),
            "candidate_exact_roots": sum(r["candidate_exact_roots"] for r in records),
            "gain": sum(r["gain"] for r in records),
            "loss": sum(r["loss"] for r in records),
        },
        "families": summary,
        "activation": {
            "eligible_runs": sum(r["candidate_mode"] == "equality_forced" for r in records),
            "force_events": sum(r["force_events"] for r in records),
            "opaque_fallback_runs": sum(r["candidate_mode"] == "opaque_numeric_fallback" for r in records),
        },
        "formal_exact_authority": False,
        "real_cases_used": False,
    }
    output = Path(__file__).with_name("D0_AGGREGATE.json")
    output.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return aggregate


if __name__ == "__main__":
    run()
