"""Independent, Gold-side reconstruction for EXP-SINGULAR-001 S4 development."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any


VARIANTS = (
    "S1-AP-LMQR",
    "S4-C2-NULLSPACE-TWO-STEP",
    "S4-ANALYTIC-TWO-STEP-CONTROL",
)


def counterbalanced_variant_order(case_index: int) -> tuple[str, str, str]:
    representation_index = (case_index - 1) % 3
    group_index = (case_index - 1) // 3
    if group_index % 2 == 0:
        return tuple(
            VARIANTS[(position + representation_index) % 3] for position in range(3)
        )
    return tuple(
        VARIANTS[(position - representation_index) % 3] for position in range(3)
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise TypeError(f"not a protocol decimal: {value!r}")
    return Decimal(str(value))


def linf(left: list[Decimal], right: list[Decimal]) -> Decimal:
    if len(left) != len(right):
        raise ValueError("configuration dimension mismatch")
    return max(
        (abs(a - b) for a, b in zip(left, right, strict=True)), default=Decimal(0)
    )


def recompute_assessment(
    row: dict[str, Any],
    manifest_case: dict[str, Any],
    gold_case: dict[str, Any],
) -> dict[str, Any]:
    promoted = row["status"] == "promoted"
    eligible = manifest_case["stratum"] == "isolated-deflation-one"
    result: dict[str, Any] = {
        "configuration_error": None,
        "configuration_error_covered": False,
        "eligible": eligible,
        "false_promotion": False,
        "gold_success": False,
        "promoted": promoted,
        "stratum": manifest_case["stratum"],
        "target_error": None,
        "target_error_covered": False,
    }
    if not promoted:
        return result
    evidence = row.get("root_evidence")
    configurations = gold_case.get("isolated_configurations", [])
    targets = gold_case.get("isolated_targets", [])
    if (
        not isinstance(evidence, dict)
        or not configurations
        or len(configurations) != len(targets)
    ):
        result["false_promotion"] = True
        return result
    endpoint = [decimal(value) for value in evidence["endpoint"]]
    distances = [
        linf(endpoint, [decimal(value) for value in configuration])
        for configuration in configurations
    ]
    nearest = min(range(len(distances)), key=distances.__getitem__)
    configuration_error = distances[nearest]
    target_error = abs(decimal(evidence["target"]) - decimal(targets[nearest]))
    configuration_covered = configuration_error <= decimal(
        evidence["configuration_error_estimate"]
    )
    target_covered = target_error <= decimal(evidence["target_error_estimate"])
    result.update(
        {
            "configuration_error": float(configuration_error),
            "configuration_error_covered": configuration_covered,
            "false_promotion": not (configuration_covered and target_covered),
            "gold_success": configuration_covered and target_covered,
            "target_error": float(target_error),
            "target_error_covered": target_covered,
        }
    )
    return result


def normalized_assessment(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    for key in ("configuration_error", "target_error"):
        if result[key] is not None:
            result[key] = float(result[key])
    return result


def assessments_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    discrete = (
        "configuration_error_covered",
        "eligible",
        "false_promotion",
        "gold_success",
        "promoted",
        "stratum",
        "target_error_covered",
    )
    if any(left[key] != right[key] for key in discrete):
        return False
    for key in ("configuration_error", "target_error"):
        if left[key] is None or right[key] is None:
            if left[key] is not right[key]:
                return False
        elif not math.isclose(
            float(left[key]),
            float(right[key]),
            rel_tol=1e-12,
            abs_tol=1e-15,
        ):
            return False
    return True


def decimal_close(left: Any, right: Any, *, relative: str = "1e-30") -> bool:
    a = decimal(left)
    b = decimal(right)
    scale = max(Decimal(1), abs(a), abs(b))
    return abs(a - b) <= Decimal(relative) * scale


def decimal_linf(values: list[Decimal]) -> Decimal:
    return max((abs(value) for value in values), default=Decimal(0))


def decimal_l1(values: list[Decimal]) -> Decimal:
    return sum((abs(value) for value in values), Decimal(0))


def decimal_norm2(values: list[Decimal]) -> Decimal:
    return sum((value * value for value in values), Decimal(0)).sqrt()


def eps_value(bits: int) -> Decimal:
    return Decimal(2) ** (1 - bits)


def eps_two_thirds(bits: int) -> Decimal:
    return (eps_value(bits) * eps_value(bits)) ** (Decimal(1) / Decimal(3))


def splitmix_coefficients(nullity: int, iteration: int) -> list[Decimal]:
    mask = (1 << 64) - 1
    namespace = 0x53342D43322D5631
    integers: list[int] = []
    for coordinate in range(1, nullity + 1):
        value = (
            namespace
            ^ ((nullity & mask) << 48)
            ^ ((iteration & mask) << 16)
            ^ coordinate
        ) & mask
        value = (value + 0x9E3779B97F4A7C15) & mask
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
        value ^= value >> 31
        magnitude = 1 + (value & 0x7FFFFFFF)
        integers.append(magnitude if (value >> 63) == 0 else -magnitude)
    frozen = [Decimal(value) for value in integers]
    magnitude = decimal_norm2(frozen)
    return [value / magnitude for value in frozen]


def pairwise_linf(points: list[list[Decimal]]) -> Decimal:
    if len(points) <= 1:
        return Decimal(0)
    return max(
        linf(points[first], points[second])
        for first in range(len(points) - 1)
        for second in range(first + 1, len(points))
    )


def dot(left: list[Decimal], right: list[Decimal]) -> Decimal:
    return sum((a * b for a, b in zip(left, right, strict=True)), Decimal(0))


def linear_combination(
    columns: list[list[Decimal]], coefficients: list[Decimal]
) -> list[Decimal]:
    if not columns:
        return []
    return [
        sum(
            (
                columns[column][row] * coefficients[column]
                for column in range(len(columns))
            ),
            Decimal(0),
        )
        for row in range(len(columns[0]))
    ]


def symmetric_eigenvalues(matrix: list[list[float]]) -> list[float]:
    values = [row[:] for row in matrix]
    dimension = len(values)
    for _ in range(100 * max(1, dimension * dimension)):
        largest = 0.0
        pair = (0, 0)
        for row in range(dimension):
            for column in range(row + 1, dimension):
                if abs(values[row][column]) > largest:
                    largest = abs(values[row][column])
                    pair = (row, column)
        if largest <= 1e-15:
            break
        first, second = pair
        angle = 0.5 * math.atan2(
            2.0 * values[first][second],
            values[second][second] - values[first][first],
        )
        cosine = math.cos(angle)
        sine = math.sin(angle)
        for index in range(dimension):
            if index in pair:
                continue
            old_first = values[index][first]
            old_second = values[index][second]
            values[index][first] = values[first][index] = (
                cosine * old_first - sine * old_second
            )
            values[index][second] = values[second][index] = (
                sine * old_first + cosine * old_second
            )
        a = values[first][first]
        b = values[first][second]
        d = values[second][second]
        values[first][first] = (
            cosine * cosine * a - 2.0 * sine * cosine * b + sine * sine * d
        )
        values[second][second] = (
            sine * sine * a + 2.0 * sine * cosine * b + cosine * cosine * d
        )
        values[first][second] = values[second][first] = 0.0
    return [values[index][index] for index in range(dimension)]


def principal_angle_sine(
    reference_columns: list[list[Decimal]],
    local_columns: list[list[Decimal]],
) -> float:
    overlap = [
        [float(dot(reference, local)) for local in local_columns]
        for reference in reference_columns
    ]
    gram = [
        [
            sum(overlap[row][left] * overlap[row][right] for row in range(len(overlap)))
            for right in range(len(local_columns))
        ]
        for left in range(len(local_columns))
    ]
    minimum_eigenvalue = max(0.0, min(symmetric_eigenvalues(gram)))
    minimum_singular = min(1.0, math.sqrt(minimum_eigenvalue))
    return math.sqrt(max(0.0, 1.0 - minimum_singular * minimum_singular))


def verify_transport(
    probe: dict[str, Any],
    reference: dict[str, Any],
    failures: list[str],
    label: str,
) -> None:
    local_columns = [
        [decimal(value) for value in column] for column in probe["right_null_basis"]
    ]
    reference_columns = [
        [decimal(value) for value in column] for column in reference["basis"]
    ]
    reference_direction = [decimal(value) for value in reference["direction"]]
    calculated_local = [dot(column, reference_direction) for column in local_columns]
    recorded_local = [decimal(value) for value in probe["c_local"]]
    if any(
        not decimal_close(left, right)
        for left, right in zip(calculated_local, recorded_local, strict=True)
    ):
        failures.append(f"{label}:transport_c_local")
    local_norm = decimal_norm2(calculated_local)
    if local_norm == 0:
        failures.append(f"{label}:transport_zero")
        return
    normalized = [value / local_norm for value in calculated_local]
    calculated_direction = linear_combination(local_columns, normalized)
    recorded_direction = [decimal(value) for value in probe["direction"]]
    if any(
        not decimal_close(left, right)
        for left, right in zip(calculated_direction, recorded_direction, strict=True)
    ):
        failures.append(f"{label}:transport_direction")
    projection = linear_combination(local_columns, calculated_local)
    projection_loss = decimal_norm2(
        [
            left - right
            for left, right in zip(reference_direction, projection, strict=True)
        ]
    )
    if not decimal_close(projection_loss, probe["projection_loss"]):
        failures.append(f"{label}:projection_loss")
    angle = principal_angle_sine(reference_columns, local_columns)
    recorded_angle = float(probe["angle_sine"])
    if abs(angle - recorded_angle) > 1e-7:
        failures.append(f"{label}:principal_angle")
    if (angle <= float(probe["subspace_angle_bound"])) != bool(
        probe["subspace_decision"]
    ):
        failures.append(f"{label}:transport_decision")


def verify_probe_trace(probe: dict[str, Any], failures: list[str], label: str) -> None:
    c_local = [decimal(value) for value in probe["c_local"]]
    if not decimal_close(decimal_norm2(c_local), probe["c_local_norm"]):
        failures.append(f"{label}:c_local_norm")
    if int(probe["ell"]) < 1:
        failures.append(f"{label}:ell")
    expected_coefficients = splitmix_coefficients(
        len(probe["coefficients"]),
        int(probe["ell"]),
    )
    recorded_coefficients = [decimal(value) for value in probe["coefficients"]]
    if not probe["transported"] and any(
        not decimal_close(left, right)
        for left, right in zip(
            expected_coefficients,
            recorded_coefficients,
            strict=True,
        )
    ):
        failures.append(f"{label}:counter_coefficients")
    angle = decimal(probe["angle_sine"])
    bound = decimal(probe["subspace_angle_bound"])
    expected_subspace = angle <= bound and decimal(probe["c_local_norm"]) > 0
    if bool(probe["subspace_decision"]) != expected_subspace:
        failures.append(f"{label}:subspace_decision")
    spectrum = [decimal(value) for value in probe["projected_spectrum"]]
    tau = decimal(probe["projected_tau"])
    expected_tau = (
        Decimal(32)
        * Decimal(len(spectrum))
        * eps_value(int(probe["precision_bits"])).sqrt()
        * max(Decimal(1), spectrum[0])
    )
    if not decimal_close(expected_tau, tau):
        failures.append(f"{label}:projected_tau")
    condition = (
        Decimal("Infinity")
        if not spectrum or spectrum[-1] == 0
        else spectrum[0] / spectrum[-1]
    )
    if not spectrum or any(value <= tau for value in spectrum):
        failures.append(f"{label}:projected_rank")
    if condition > Decimal("1e12") or not decimal_close(
        condition, probe["projected_condition"]
    ):
        failures.append(f"{label}:projected_condition")


def verify_applicability(row: dict[str, Any]) -> list[str]:
    if row["variant"] == "S1-AP-LMQR" or row["status"] != "promoted":
        return []
    failures: list[str] = []
    diagnostics = row["diagnostics"]
    route = diagnostics.get("initial_route")
    if not isinstance(route, dict):
        return ["missing_initial_route"]
    expected_probe_count = 4 if row["variant"] == "S4-C2-NULLSPACE-TWO-STEP" else 2
    if len(route["probes"]) != expected_probe_count:
        failures.append("initial_route_probe_count")
    for index, probe in enumerate(route["probes"]):
        verify_probe_trace(probe, failures, f"route[{index}]")
        singular = [decimal(value) for value in probe["singular_values"]]
        bits = int(probe["precision_bits"])
        expected_rank_tau = (
            Decimal(32)
            * Decimal(len(singular))
            * eps_value(bits)
            * max(Decimal(1), singular[0])
        )
        if not decimal_close(expected_rank_tau, probe["tau_rank"]):
            failures.append(f"route[{index}]:tau_rank")
        if decimal(probe["residual_linf"]) > Decimal("1.5625e-14"):
            failures.append(f"route[{index}]:residual_goal")
        retained = int(probe["rank"])
        tau = decimal(probe["tau_rank"])
        qualifying = [
            position
            for position in range(1, len(singular))
            if singular[position - 1] > tau
            and singular[position] / singular[position - 1] <= Decimal("1e-6")
        ]
        if not qualifying or qualifying[0] != retained:
            failures.append(f"route[{index}]:smallest_gap")
    reference_probe = next(
        probe
        for probe in route["probes"]
        if int(probe["precision_bits"]) == 256
        and (
            row["variant"] == "S4-ANALYTIC-TWO-STEP-CONTROL"
            or float(probe["jacobian_radius_multiplier"]) == 0.5
        )
    )
    reference_left = [
        [decimal(value) for value in column]
        for column in reference_probe["left_null_basis"]
    ]
    reference_right = [
        [decimal(value) for value in column]
        for column in reference_probe["right_null_basis"]
    ]
    left_angles: list[float] = []
    right_angles: list[float] = []
    for probe in route["probes"]:
        if probe is reference_probe:
            continue
        left_angles.append(
            principal_angle_sine(
                reference_left,
                [
                    [decimal(value) for value in column]
                    for column in probe["left_null_basis"]
                ],
            )
        )
        right_angles.append(
            principal_angle_sine(
                reference_right,
                [
                    [decimal(value) for value in column]
                    for column in probe["right_null_basis"]
                ],
            )
        )
    if max(left_angles, default=0.0) > 1e-6 or max(right_angles, default=0.0) > 1e-6:
        failures.append("initial_route_angles")
    if row["variant"] == "S4-C2-NULLSPACE-TWO-STEP":
        if (
            abs(float(route["maximum_left_angle_sine"]) - max(left_angles, default=0.0))
            > 1e-7
        ):
            failures.append("initial_left_angle_binding")
        if (
            abs(
                float(route["maximum_right_angle_sine"])
                - max(right_angles, default=0.0)
            )
            > 1e-7
        ):
            failures.append("initial_right_angle_binding")
    else:
        if abs(float(route["left_angle_sine"]) - max(left_angles, default=0.0)) > 1e-7:
            failures.append("initial_left_angle_binding")
        if (
            abs(float(route["right_angle_sine"]) - max(right_angles, default=0.0))
            > 1e-7
        ):
            failures.append("initial_right_angle_binding")
    audits = diagnostics.get("applicability_audits", [])
    if len(audits) != 4:
        failures.append("trajectory_audit_count")
    trajectories = {
        item["identity"]: item
        for key in ("primary_trajectories", "confirmation_trajectories")
        for item in diagnostics.get(key, [])
    }
    for audit_index, audit in enumerate(audits):
        if not audit.get("decision", False):
            failures.append(f"audit[{audit_index}]:decision")
        identity = audit["identity"]
        if identity not in trajectories:
            failures.append(f"audit[{audit_index}]:identity")
            continue
        trajectory = trajectories[identity]
        trajectory_start = [decimal(value) for value in trajectory["start"]]
        trajectory_final = [decimal(value) for value in trajectory["endpoint"]]
        expected_normalized_step = decimal(trajectory["last_step"]) / max(
            Decimal(1),
            decimal_linf(trajectory_final),
        )
        reference = audit["physical_reference"]
        if int(reference["ell"]) != 65:
            failures.append(f"audit[{audit_index}]:reference_ell")
        if not decimal_close(
            decimal_norm2([decimal(value) for value in reference["direction"]]),
            Decimal(1),
        ):
            failures.append(f"audit[{audit_index}]:reference_direction_norm")
        reference_columns = [
            [decimal(value) for value in column] for column in reference["basis"]
        ]
        reference_coefficients = [decimal(value) for value in reference["coefficients"]]
        expected_reference_coefficients = splitmix_coefficients(
            len(reference_coefficients),
            65,
        )
        if any(
            not decimal_close(left, right)
            for left, right in zip(
                reference_coefficients,
                expected_reference_coefficients,
                strict=True,
            )
        ):
            failures.append(f"audit[{audit_index}]:reference_counter")
        reconstructed_reference = linear_combination(
            reference_columns,
            reference_coefficients,
        )
        reference_norm = decimal_norm2(reconstructed_reference)
        if reference_norm == 0:
            failures.append(f"audit[{audit_index}]:reference_zero")
        else:
            reconstructed_reference = [
                value / reference_norm for value in reconstructed_reference
            ]
            recorded_reference = [decimal(value) for value in reference["direction"]]
            if any(
                not decimal_close(left, right)
                for left, right in zip(
                    reconstructed_reference,
                    recorded_reference,
                    strict=True,
                )
            ):
                failures.append(f"audit[{audit_index}]:reference_counter_relation")
        if len(audit["probes"]) != expected_probe_count:
            failures.append(f"audit[{audit_index}]:probe_count")
        for probe_index, entry in enumerate(audit["probes"]):
            start = entry["start"]
            final = entry["final"]
            verify_probe_trace(
                start, failures, f"audit[{audit_index}].start[{probe_index}]"
            )
            verify_probe_trace(
                final, failures, f"audit[{audit_index}].final[{probe_index}]"
            )
            verify_transport(
                start,
                reference,
                failures,
                f"audit[{audit_index}].start[{probe_index}]",
            )
            verify_transport(
                final,
                reference,
                failures,
                f"audit[{audit_index}].final[{probe_index}]",
            )
            if int(start["ell"]) != 65 or int(final["ell"]) != 65:
                failures.append(f"audit[{audit_index}].probe[{probe_index}]:ell")
            for side, probe, expected_point in (
                ("start", start, trajectory_start),
                ("final", final, trajectory_final),
            ):
                if any(
                    not decimal_close(left, right)
                    for left, right in zip(
                        [decimal(value) for value in probe["point"]],
                        expected_point,
                        strict=True,
                    )
                ):
                    failures.append(
                        f"audit[{audit_index}].probe[{probe_index}]:{side}_point"
                    )
            start_spectrum = [decimal(value) for value in start["projected_spectrum"]]
            final_spectrum = [decimal(value) for value in final["projected_spectrum"]]
            ratios = [
                b / a for a, b in zip(start_spectrum, final_spectrum, strict=True)
            ]
            recorded = [
                decimal(value) for value in entry["order_persistence"]["ratios"]
            ]
            if len(ratios) != len(recorded) or any(
                not decimal_close(left, right)
                for left, right in zip(ratios, recorded, strict=True)
            ):
                failures.append(
                    f"audit[{audit_index}].probe[{probe_index}]:order_ratios"
                )
            order_expected = all(
                Decimal(1) / Decimal(16) <= value <= Decimal(16) for value in ratios
            )
            if bool(entry["order_persistence"]["decision"]) != order_expected:
                failures.append(
                    f"audit[{audit_index}].probe[{probe_index}]:order_decision"
                )
            null_decay = entry["null_decay"]
            bits = int(entry["precision_bits"])
            singular = [decimal(value) for value in final["singular_values"]]
            retained = int(final["rank"])
            discarded = max(singular[retained:]) / max(Decimal(1), singular[0])
            if not decimal_close(
                discarded,
                null_decay["normalized_discarded_sigma"],
            ):
                failures.append(
                    f"audit[{audit_index}].probe[{probe_index}]:discarded_sigma"
                )
            if not decimal_close(
                expected_normalized_step,
                null_decay["normalized_last_step"],
            ):
                failures.append(
                    f"audit[{audit_index}].probe[{probe_index}]:normalized_step"
                )
            expected_null_bound = Decimal(16) * (
                decimal(null_decay["normalized_last_step"]) ** 2 + eps_two_thirds(bits)
            )
            if not decimal_close(
                expected_null_bound, null_decay["bound"], relative="1e-30"
            ):
                failures.append(f"audit[{audit_index}].probe[{probe_index}]:null_bound")
            null_expected = decimal(
                null_decay["normalized_discarded_sigma"]
            ) <= decimal(null_decay["bound"])
            if bool(null_decay["decision"]) != null_expected:
                failures.append(f"audit[{audit_index}].probe[{probe_index}]:null_decay")
        if len(audit["residual_decay"]) != 2:
            failures.append(f"audit[{audit_index}]:residual_count")
        for residual_index, residual in enumerate(audit["residual_decay"]):
            residual_bits = int(residual["precision_bits"])
            source_entry = next(
                entry
                for entry in audit["probes"]
                if int(entry["precision_bits"]) == residual_bits
                and (
                    row["variant"] == "S4-ANALYTIC-TWO-STEP-CONTROL"
                    or float(entry["radius_multiplier"]) == 1.0
                )
            )
            start_probe = source_entry["start"]
            final_probe = source_entry["final"]
            start_scale = max(
                Decimal(1),
                decimal(start_probe["residual_linf"]),
                decimal(start_probe["jacobian_inf_norm"])
                * max(
                    Decimal(1),
                    decimal_linf([decimal(value) for value in start_probe["point"]]),
                ),
            )
            residual_ratio = decimal(final_probe["residual_linf"]) / start_scale
            if not decimal_close(start_scale, residual["F_scale"]):
                failures.append(
                    f"audit[{audit_index}].residual[{residual_index}]:F_scale"
                )
            if not decimal_close(residual_ratio, residual["residual_ratio"]):
                failures.append(
                    f"audit[{audit_index}].residual[{residual_index}]:ratio"
                )
            expected_residual_bound = Decimal(16) * (
                decimal(residual["normalized_last_step"]) ** 2
                + eps_two_thirds(int(residual["precision_bits"]))
            )
            if not decimal_close(
                expected_residual_bound,
                residual["bound"],
                relative="1e-30",
            ):
                failures.append(
                    f"audit[{audit_index}].residual[{residual_index}]:bound"
                )
            expected = decimal(residual["residual_ratio"]) <= decimal(residual["bound"])
            if bool(residual["decision"]) != expected:
                failures.append(
                    f"audit[{audit_index}].residual[{residual_index}]:decision"
                )
    return failures


def verify_error_audit(row: dict[str, Any]) -> list[str]:
    if row["variant"] == "S1-AP-LMQR" or row["status"] != "promoted":
        return []
    failures: list[str] = []
    audit = row["diagnostics"]["error_audit"]
    corrections = {
        key: [decimal(value) for value in vector]
        for key, vector in audit["final_corrections"].items()
    }
    correction_order = (
        (
            "q128_radius_1",
            "q128_radius_0.5",
            "q256_radius_1",
            "q256_radius_0.5",
        )
        if row["variant"] == "S4-C2-NULLSPACE-TWO-STEP"
        else ("q128", "q256")
    )
    norms = [decimal_linf(corrections[key]) for key in correction_order]
    applicability = row["diagnostics"].get("applicability_audits", [])
    if len(applicability) >= 2:
        expected_corrections: dict[str, list[Decimal]] = {}
        for key, audit_index, bits, radius in (
            ("q128_radius_1", 0, 128, 1.0),
            ("q128_radius_0.5", 0, 128, 0.5),
            ("q256_radius_1", 1, 256, 1.0),
            ("q256_radius_0.5", 1, 256, 0.5),
        ):
            if row["variant"] == "S4-C2-NULLSPACE-TWO-STEP":
                entry = next(
                    probe
                    for probe in applicability[audit_index]["probes"]
                    if int(probe["precision_bits"]) == bits
                    and float(probe["radius_multiplier"]) == radius
                )
                expected_corrections[key] = [
                    decimal(value) for value in entry["final"]["complete_correction"]
                ]
        if row["variant"] == "S4-ANALYTIC-TWO-STEP-CONTROL":
            for key, audit_index, bits in (("q128", 0, 128), ("q256", 1, 256)):
                entry = next(
                    probe
                    for probe in applicability[audit_index]["probes"]
                    if int(probe["precision_bits"]) == bits
                )
                expected_corrections[key] = [
                    decimal(value) for value in entry["final"]["complete_correction"]
                ]
        for key, expected_vector in expected_corrections.items():
            if any(
                not decimal_close(left, right)
                for left, right in zip(expected_vector, corrections[key], strict=True)
            ):
                failures.append(f"final_correction_binding_{key}")
    recorded_norms = [decimal(value) for value in audit["final_correction_norms"]]
    if len(norms) != len(recorded_norms) or any(
        not decimal_close(left, right)
        for left, right in zip(norms, recorded_norms, strict=True)
    ):
        failures.append("final_correction_norms")
    q_magnitude = max(norms)
    if not decimal_close(q_magnitude, audit["final_correction_magnitude"]):
        failures.append("final_correction_magnitude")
    scales = audit["roundoff_scales"]
    s128 = decimal(scales["s128"])
    s256 = decimal(scales["s256"])
    if row["variant"] == "S4-C2-NULLSPACE-TWO-STEP":
        radius_components = [
            linf(corrections["q128_radius_1"], corrections["q128_radius_0.5"]) + s128,
            linf(corrections["q256_radius_1"], corrections["q256_radius_0.5"]) + s256,
        ]
        precision_components = [
            linf(corrections["q256_radius_1"], corrections["q128_radius_1"])
            + max(s128, s256),
            linf(corrections["q256_radius_0.5"], corrections["q128_radius_0.5"])
            + max(s128, s256),
        ]
        correction_reserve = max(*radius_components, *precision_components)
        expected_radius = [
            decimal(value) for value in audit["radius_reserve_components"]
        ]
        expected_precision = [
            decimal(value) for value in audit["precision_reserve_components"]
        ]
        if any(
            not decimal_close(left, right)
            for left, right in zip(radius_components, expected_radius, strict=True)
        ):
            failures.append("radius_reserve_components")
        if any(
            not decimal_close(left, right)
            for left, right in zip(
                precision_components, expected_precision, strict=True
            )
        ):
            failures.append("precision_reserve_components")
    else:
        correction_reserve = linf(corrections["q256"], corrections["q128"]) + max(
            s128, s256
        )
    if not decimal_close(correction_reserve, audit["correction_reserve"]):
        failures.append("correction_reserve")
    sources = audit["configuration_sources"]
    endpoint128 = [decimal(value) for value in sources["primary_128_endpoint"]]
    endpoint256 = [decimal(value) for value in sources["primary_256_endpoint"]]
    confirmation_points = [
        [decimal(value) for value in point]
        for point in sources["confirmation_endpoints"]
    ]
    primary_traces = {
        int(item["precision_bits"]): item
        for item in row["diagnostics"].get("primary_trajectories", [])
    }
    confirmation_traces = row["diagnostics"].get("confirmation_trajectories", [])
    if primary_traces:
        for bits, endpoint, last_step in (
            (128, endpoint128, decimal(sources["primary_128_last_step"])),
            (256, endpoint256, decimal(sources["primary_256_last_step"])),
        ):
            trace = primary_traces[bits]
            if any(
                not decimal_close(left, right)
                for left, right in zip(
                    endpoint,
                    [decimal(value) for value in trace["endpoint"]],
                    strict=True,
                )
            ) or not decimal_close(last_step, trace["last_step"]):
                failures.append(f"configuration_source_binding_{bits}")
    if confirmation_traces and len(confirmation_traces) == len(confirmation_points):
        for index, (point, trace) in enumerate(
            zip(confirmation_points, confirmation_traces, strict=True)
        ):
            if any(
                not decimal_close(left, right)
                for left, right in zip(
                    point,
                    [decimal(value) for value in trace["endpoint"]],
                    strict=True,
                )
            ):
                failures.append(f"confirmation_source_binding_{index}")
    expected_s128 = eps_two_thirds(128) * max(Decimal(1), decimal_linf(endpoint128))
    expected_s256 = eps_two_thirds(256) * max(Decimal(1), decimal_linf(endpoint256))
    if not decimal_close(expected_s128, s128, relative="1e-30"):
        failures.append("s128")
    if not decimal_close(expected_s256, s256, relative="1e-30"):
        failures.append("s256")
    raw_components = [
        decimal(sources["primary_128_last_step"]),
        decimal(sources["primary_256_last_step"]),
        linf(endpoint256, endpoint128),
        pairwise_linf([endpoint256, *confirmation_points]),
        correction_reserve,
        q_magnitude,
    ]
    recorded_raw = [decimal(value) for value in audit["raw_configuration_components"]]
    if len(raw_components) != len(recorded_raw) or any(
        not decimal_close(left, right)
        for left, right in zip(raw_components, recorded_raw, strict=True)
    ):
        failures.append("raw_configuration_components")
    raw_x = max(raw_components)
    configuration_error = Decimal(16) * raw_x
    if not decimal_close(raw_x, audit["raw_configuration_error"]):
        failures.append("raw_configuration_error")
    if not decimal_close(configuration_error, audit["configuration_error"]):
        failures.append("configuration_error")
    gradients = {
        (int(item["precision_bits"]), str(item["radius_multiplier"])): (
            [decimal(value) for value in item["values"]],
            decimal(item["uncertainty"]),
        )
        for item in audit["gradients"]
    }
    for (bits, _radius), (gradient, uncertainty) in gradients.items():
        expected_uncertainty = eps_two_thirds(bits) * max(
            Decimal(1),
            decimal_l1(gradient),
        )
        if not decimal_close(expected_uncertainty, uncertainty, relative="1e-30"):
            failures.append(f"gradient_uncertainty_{bits}")
    gradient_radius_components = []
    for bits in (128, 256):
        full, full_u = gradients[(bits, "1.0")]
        half, half_u = gradients[(bits, "0.5")]
        gradient_radius_components.append(
            decimal_l1([a - b for a, b in zip(full, half, strict=True)])
            + max(full_u, half_u)
        )
    gradient_precision_components = []
    for radius in ("1.0", "0.5"):
        low, low_u = gradients[(128, radius)]
        high, high_u = gradients[(256, radius)]
        gradient_precision_components.append(
            decimal_l1([a - b for a, b in zip(high, low, strict=True)])
            + max(low_u, high_u)
        )
    gradient_reserve = max(*gradient_radius_components, *gradient_precision_components)
    recorded_gradient_radius = [
        decimal(value) for value in audit["gradient_radius_components"]
    ]
    recorded_gradient_precision = [
        decimal(value) for value in audit["gradient_precision_components"]
    ]
    if any(
        not decimal_close(left, right)
        for left, right in zip(
            gradient_radius_components,
            recorded_gradient_radius,
            strict=True,
        )
    ):
        failures.append("gradient_radius_components")
    if any(
        not decimal_close(left, right)
        for left, right in zip(
            gradient_precision_components,
            recorded_gradient_precision,
            strict=True,
        )
    ):
        failures.append("gradient_precision_components")
    if not decimal_close(gradient_reserve, audit["gradient_reserve"]):
        failures.append("gradient_reserve")
    target_values = audit["target_values"]
    target128 = decimal(target_values["primary_128"])
    target256 = decimal(target_values["primary_256"])
    confirmations = [decimal(value) for value in target_values["confirmation"]]
    if primary_traces:
        if not decimal_close(target128, primary_traces[128]["target"]):
            failures.append("target_source_binding_128")
        if not decimal_close(target256, primary_traces[256]["target"]):
            failures.append("target_source_binding_256")
    if confirmation_traces and len(confirmations) == len(confirmation_traces):
        for index, (target, trace) in enumerate(
            zip(confirmations, confirmation_traces, strict=True)
        ):
            if not decimal_close(target, trace["target"]):
                failures.append(f"target_confirmation_binding_{index}")
    target_precision = abs(target256 - target128)
    target_confirmation = max(
        (
            abs(left - right)
            for left in [target256, *confirmations]
            for right in [target256, *confirmations]
        ),
        default=Decimal(0),
    )
    target_roundoff = max(
        eps_value(128) * max(Decimal(1), abs(target128)),
        eps_value(256) * max(Decimal(1), abs(target256)),
    )
    if not decimal_close(target_roundoff, audit["target_roundoff"], relative="1e-30"):
        failures.append("target_roundoff")
    gradient256 = gradients[(256, "1.0")][0]
    target_components = [
        target_precision,
        target_confirmation,
        decimal_l1(gradient256) * raw_x,
        gradient_reserve * raw_x,
        target_roundoff,
    ]
    recorded_target_components = [
        decimal(value) for value in audit["target_error_components"]
    ]
    if any(
        not decimal_close(left, right)
        for left, right in zip(
            target_components, recorded_target_components, strict=True
        )
    ):
        failures.append("target_error_components")
    target_error = Decimal(16) * max(target_components)
    if not decimal_close(target_error, audit["target_error"]):
        failures.append("target_error")
    decision = configuration_error <= Decimal("1e-10") and target_error <= Decimal(
        "1e-12"
    )
    if bool(audit["decision"]) != decision:
        failures.append("error_decision")
    return failures


def verify_root_and_semantic_binding(row: dict[str, Any]) -> list[str]:
    if row["variant"] == "S1-AP-LMQR" or row["status"] != "promoted":
        return []
    failures: list[str] = []
    diagnostics = row["diagnostics"]
    primary = {
        int(item["precision_bits"]): item
        for item in diagnostics["primary_trajectories"]
    }
    confirmations = diagnostics["confirmation_trajectories"]
    root = row["root_evidence"]
    endpoint = [decimal(value) for value in root["endpoint"]]
    primary_endpoint = [decimal(value) for value in primary[256]["endpoint"]]
    if any(
        not decimal_close(left, right)
        for left, right in zip(endpoint, primary_endpoint, strict=True)
    ):
        failures.append("root_endpoint")
    if not decimal_close(root["target"], primary[256]["target"]):
        failures.append("root_target")
    if not decimal_close(root["residual_linf"], primary[256]["residual_linf"]):
        failures.append("root_residual")
    expected_confirmation_endpoints = [item["endpoint"] for item in confirmations]
    expected_confirmation_targets = [item["target"] for item in confirmations]
    expected_confirmation_residuals = [item["residual_linf"] for item in confirmations]
    for label, observed, expected in (
        (
            "confirmation_endpoint",
            root["confirmation_endpoints"],
            expected_confirmation_endpoints,
        ),
        (
            "confirmation_target",
            root["confirmation_targets"],
            expected_confirmation_targets,
        ),
        (
            "confirmation_residual",
            root["confirmation_residuals"],
            expected_confirmation_residuals,
        ),
    ):
        if len(observed) != len(expected):
            failures.append(f"root_{label}_count")
            continue
        if label == "confirmation_endpoint":
            mismatch = any(
                any(
                    not decimal_close(left, right)
                    for left, right in zip(
                        [decimal(value) for value in observed_point],
                        [decimal(value) for value in expected_point],
                        strict=True,
                    )
                )
                for observed_point, expected_point in zip(
                    observed, expected, strict=True
                )
            )
        else:
            mismatch = any(
                not decimal_close(left, right)
                for left, right in zip(observed, expected, strict=True)
            )
        if mismatch:
            failures.append(f"root_{label}")
    route = diagnostics["initial_route"]
    if int(root["numerical_rank"]) != int(route["selected_rank"]):
        failures.append("root_rank")
    if int(root["nullity"]) != int(route["nullity"]):
        failures.append("root_nullity")
    route_condition = max(decimal(probe["condition"]) for probe in route["probes"])
    if not decimal_close(root["condition_estimate"], route_condition):
        failures.append("root_condition")
    if not (
        root["rank_stable"]
        and root["independent_confirmations_passed"]
        and root["canonical_confirmations_passed"]
        and root["linear_trace_passed"]
    ):
        failures.append("root_boolean_gates")
    if int(root["precision_bits"]) != 256 or root["precision_stages"] != [128, 256]:
        failures.append("root_precision")
    expected_signatures = []
    for probe in route["probes"]:
        signature = {
            "nullity": int(probe["nullity"]),
            "precision_bits": int(probe["precision_bits"]),
            "rank": int(probe["rank"]),
        }
        if row["variant"] == "S4-C2-NULLSPACE-TWO-STEP":
            signature["radius_multiplier"] = float(probe["jacobian_radius_multiplier"])
        expected_signatures.append(signature)
    if root["route_rank_signatures"] != expected_signatures:
        failures.append("root_route_signatures")
    semantic_traces = diagnostics["semantic_replays"]
    if len(semantic_traces) != 4:
        failures.append("semantic_trace_count")
    trajectory_sequence = [primary[128], primary[256], *confirmations]
    for index, (semantic, trajectory) in enumerate(
        zip(semantic_traces, trajectory_sequence, strict=True)
    ):
        if not semantic["accepted"]:
            failures.append(f"semantic_{index}_decision")
        if any(
            not decimal_close(left, right)
            for left, right in zip(
                [decimal(value) for value in semantic["endpoint"]],
                [decimal(value) for value in trajectory["endpoint"]],
                strict=True,
            )
        ):
            failures.append(f"semantic_{index}_endpoint")
        if not decimal_close(semantic["target"], trajectory["target"]):
            failures.append(f"semantic_{index}_target")
    row_semantic = row["semantic_replay"]
    primary_semantic = semantic_traces[1]
    if (
        row_semantic["accepted"] != primary_semantic["accepted"]
        or int(row_semantic["precision_bits"])
        != int(primary_semantic["precision_bits"])
        or not decimal_close(
            row_semantic["residual_linf"], primary_semantic["residual_linf"]
        )
        or not decimal_close(row_semantic["target"], primary_semantic["target"])
    ):
        failures.append("row_semantic_binding")
    return failures


def verify_work_accounting(row: dict[str, Any]) -> list[str]:
    work = row["work"]
    failures: list[str] = []
    categorized = work["residual_calls"] + work["target_calls"] + work["jacobian_calls"]
    if categorized != work["callbacks"]:
        failures.append("work_callback_categories")
    calls_by_precision = work["calls_by_precision"]
    if sum(item["callbacks"] for item in calls_by_precision) != work["callbacks"]:
        failures.append("work_precision_sum")
    expected_equivalent = sum(
        item["callbacks"] * math.ceil(item["precision_bits"] / 53)
        for item in calls_by_precision
    )
    if expected_equivalent != work["precision_equivalent_oracle_work"]:
        failures.append("work_precision_equivalent")
    expected_maximum = max(
        (item["precision_bits"] for item in calls_by_precision),
        default=0,
    )
    if expected_maximum != work["maximum_precision_bits"]:
        failures.append("work_maximum_precision")
    if row["variant"] != "S1-AP-LMQR":
        trajectory_iterations = sum(
            item["iterations"]
            for key in ("primary_trajectories", "confirmation_trajectories")
            for item in row["diagnostics"].get(key, [])
        )
        if trajectory_iterations != work["iterations"]:
            failures.append("work_iterations")
        if row["status"] == "promoted":
            dimension = len(row["root_evidence"]["endpoint"])
            nullity = int(row["root_evidence"]["nullity"])
            expected_target_calls = 8 + 8 * dimension
            if row["variant"] == "S4-C2-NULLSPACE-TWO-STEP":
                expected_callbacks = (
                    4 * (1 + 2 * dimension + 4 * nullity)
                    + trajectory_iterations * (4 * dimension + 4 * nullity + 2)
                    + 4
                    + 4 * (26 * dimension + 8 + 32 * nullity)
                    + 8
                    + 8 * dimension
                )
                expected_jacobian_calls = 0
                expected_factorizations = 114 + 2 * trajectory_iterations
            else:
                expected_callbacks = (
                    2 * (nullity + 2)
                    + trajectory_iterations * (nullity + 4)
                    + 4
                    + 4 * (4 * nullity + 11)
                    + 8
                    + 8 * dimension
                )
                expected_jacobian_calls = 30 + 2 * trajectory_iterations
                expected_factorizations = 58 + 2 * trajectory_iterations
            if work["callbacks"] != expected_callbacks:
                failures.append("work_exact_callbacks")
            if work["target_calls"] != expected_target_calls:
                failures.append("work_exact_target_calls")
            if work["jacobian_calls"] != expected_jacobian_calls:
                failures.append("work_exact_jacobian_calls")
            if work["factorization_calls"] != expected_factorizations:
                failures.append("work_exact_factorizations")
    if work["factorization_calls"] < 0 or work["elapsed_seconds"] < 0:
        failures.append("work_nonnegative")
    return failures


def route_signature(row: dict[str, Any]) -> str:
    diagnostics = row["diagnostics"]
    route = diagnostics.get("initial_route")
    if route is not None:
        return f"rank={route['selected_rank']}:nullity={route['nullity']}"
    return f"failed:{diagnostics.get('failure', {}).get('reason', row['reason'])}"


def analyze(
    raw: dict[str, Any],
    summary: dict[str, Any],
    manifest: dict[str, Any],
    gold: dict[str, Any],
) -> dict[str, Any]:
    rows = raw["rows"]
    if raw["schema"] != "geotarget.singular-s4-development-raw/v1":
        raise ValueError("unexpected raw schema")
    if len(rows) != 108:
        raise ValueError(f"expected 108 rows, got {len(rows)}")
    manifest_cases = {case["id"]: case for case in manifest["cases"]}
    gold_cases = {case["case_id"]: case for case in gold["cases"]}
    if set(manifest_cases) != set(gold_cases) or len(manifest_cases) != 36:
        raise ValueError("candidate/Gold case join mismatch")
    grid = {(row["case_id"], row["variant"]) for row in rows}
    expected_grid = {
        (case_id, variant) for case_id in manifest_cases for variant in VARIANTS
    }
    if grid != expected_grid or len(grid) != len(rows):
        raise ValueError("raw case/variant grid is incomplete or duplicated")
    if [row["execution_index"] for row in rows] != list(range(1, 109)):
        raise ValueError("execution order is not the frozen total order")

    assessment_mismatches: list[dict[str, Any]] = []
    reconstructed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        case_id = row["case_id"]
        expected = recompute_assessment(
            row, manifest_cases[case_id], gold_cases[case_id]
        )
        reconstructed[(case_id, row["variant"])] = expected
        observed = normalized_assessment(row["assessment"])
        if not assessments_equal(observed, normalized_assessment(expected)):
            assessment_mismatches.append(
                {
                    "case_id": case_id,
                    "expected": expected,
                    "observed": observed,
                    "variant": row["variant"],
                }
            )

    variant_summaries: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        selected = [row for row in rows if row["variant"] == variant]
        eligible = [
            row
            for row in selected
            if reconstructed[(row["case_id"], variant)]["eligible"]
        ]
        variant_summaries[variant] = {
            "budget_or_deadline_promotions": sum(
                row["status"] == "promoted"
                and (row["work"]["budget_exhausted"] or row["work"]["deadline_reached"])
                for row in selected
            ),
            "diagnostic_only": sum(
                row["status"] == "diagnostic_only" for row in selected
            ),
            "eligible_gold_successes": sum(
                reconstructed[(row["case_id"], variant)]["gold_success"]
                for row in eligible
            ),
            "eligible_instances": len(eligible),
            "false_promotions": sum(
                reconstructed[(row["case_id"], variant)]["false_promotion"]
                for row in selected
            ),
            "gold_successes": sum(
                reconstructed[(row["case_id"], variant)]["gold_success"]
                for row in selected
            ),
            "promoted": sum(row["status"] == "promoted" for row in selected),
            "total": len(selected),
            "unknown": sum(row["status"] == "unknown" for row in selected),
            "variant": variant,
        }

    metamorphic: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["variant"], row["metamorphic_group"])].append(row)
    for (variant, group), selected in sorted(grouped.items()):
        promotions = {row["status"] == "promoted" for row in selected}
        successes = {
            reconstructed[(row["case_id"], variant)]["gold_success"] for row in selected
        }
        routes = (
            {"paired-baseline"}
            if variant == "S1-AP-LMQR"
            else {route_signature(row) for row in selected}
        )
        if len(promotions) != 1 or len(successes) != 1 or len(routes) != 1:
            metamorphic.append({"group": group, "variant": variant})

    by_key = {(row["case_id"], row["variant"]): row for row in rows}
    control_disagreements: list[str] = []
    for case_id in sorted(manifest_cases):
        candidate = by_key[(case_id, "S4-C2-NULLSPACE-TWO-STEP")]
        control = by_key[(case_id, "S4-ANALYTIC-TWO-STEP-CONTROL")]
        if (
            candidate["status"] != control["status"]
            or reconstructed[(case_id, candidate["variant"])]["gold_success"]
            != reconstructed[(case_id, control["variant"])]["gold_success"]
        ):
            control_disagreements.append(case_id)

    noneligible_promotions = [
        (row["case_id"], row["variant"])
        for row in rows
        if row["variant"] != "S1-AP-LMQR"
        and not reconstructed[(row["case_id"], row["variant"])]["eligible"]
        and row["status"] == "promoted"
    ]
    evidence_failures: list[tuple[str, str]] = []
    mechanical_audit_failures: list[dict[str, Any]] = []
    budget_violations: list[tuple[str, str]] = []
    work_accounting_failures: list[dict[str, Any]] = []
    for row in rows:
        work = row["work"]
        work_failures = verify_work_accounting(row)
        if work_failures:
            work_accounting_failures.append(
                {
                    "case_id": row["case_id"],
                    "failures": work_failures,
                    "variant": row["variant"],
                }
            )
        wall = 10.0
        if (
            work_failures
            or work["callbacks"] > 4096
            or work["iterations"] > 64
            or work["elapsed_seconds"] > wall
            or (
                row["status"] == "promoted"
                and (work["budget_exhausted"] or work["deadline_reached"])
            )
        ):
            budget_violations.append((row["case_id"], row["variant"]))
        if row["status"] != "promoted":
            continue
        assessment = reconstructed[(row["case_id"], row["variant"])]
        failed = (
            row.get("root_evidence") is None
            or row.get("semantic_replay") is None
            or not row["semantic_replay"]["accepted"]
            or not assessment["configuration_error_covered"]
            or not assessment["target_error_covered"]
        )
        if row["variant"] != "S1-AP-LMQR":
            diagnostics = row["diagnostics"]
            failed = failed or diagnostics.get("phase") != "promoted"
            failed = failed or not diagnostics.get("error_audit", {}).get(
                "decision", False
            )
            failed = failed or any(
                not audit.get("decision", False)
                for audit in diagnostics.get("applicability_audits", [])
            )
            mechanical = (
                verify_applicability(row)
                + verify_error_audit(row)
                + verify_root_and_semantic_binding(row)
                + work_failures
            )
            root = row["root_evidence"]
            if root is not None:
                if not decimal_close(
                    root["configuration_error_estimate"],
                    diagnostics["error_audit"]["configuration_error"],
                ):
                    mechanical.append("root_configuration_error_binding")
                if not decimal_close(
                    root["target_error_estimate"],
                    diagnostics["error_audit"]["target_error"],
                ):
                    mechanical.append("root_target_error_binding")
            if mechanical:
                mechanical_audit_failures.append(
                    {
                        "case_id": row["case_id"],
                        "failures": mechanical,
                        "variant": row["variant"],
                    }
                )
                failed = True
        if failed:
            evidence_failures.append((row["case_id"], row["variant"]))

    candidate = variant_summaries["S4-C2-NULLSPACE-TWO-STEP"]
    baseline = variant_summaries["S1-AP-LMQR"]
    candidate_rate = Decimal(candidate["eligible_gold_successes"]) / Decimal(
        candidate["eligible_instances"]
    )
    baseline_rate = Decimal(baseline["eligible_gold_successes"]) / Decimal(
        candidate["eligible_instances"]
    )
    gain = candidate_rate - baseline_rate
    gates = {
        "candidate_control_decisions_identical": not control_disagreements,
        "candidate_gain_at_least_60_percentage_points": gain >= Decimal("0.60"),
        "candidate_recovers_at_least_12_of_15": candidate["eligible_instances"] == 15
        and candidate["eligible_gold_successes"] >= 12,
        "control_strata_unpromoted": not noneligible_promotions,
        "false_promotions_zero": sum(
            value["false_promotions"] for value in variant_summaries.values()
        )
        == 0,
        "hard_budget_violations_zero": not budget_violations
        and not work_accounting_failures,
        "metamorphic_disagreements_zero": not metamorphic,
        "promoted_evidence_failures_zero": not evidence_failures,
    }
    summary_mismatches: list[str] = []
    if summary["variant_summaries"] != variant_summaries:
        summary_mismatches.append("variant_summaries")
    if summary["advancement_gate"] != gates:
        summary_mismatches.append("advancement_gate")
    if bool(summary["development_gate_passed"]) != all(gates.values()):
        summary_mismatches.append("development_gate_passed")
    if not math.isclose(
        float(summary["candidate_gain_over_s1"]), float(gain), abs_tol=1e-15
    ):
        summary_mismatches.append("candidate_gain_over_s1")
    if not math.isclose(
        float(summary["candidate_eligible_recovery_rate"]),
        float(candidate_rate),
        abs_tol=1e-15,
    ):
        summary_mismatches.append("candidate_eligible_recovery_rate")
    expected_decision = (
        "advance-to-family-disjoint-locked-validation"
        if all(gates.values())
        else "record-bounded-S4-negative-and-continue"
    )
    if summary["decision"] != expected_decision:
        summary_mismatches.append("decision")
    if summary.get("product_connected") is not False:
        summary_mismatches.append("product_connected")
    if summary.get("locked_inputs_materialized") is not False:
        summary_mismatches.append("locked_inputs_materialized")
    if summary.get("experiment_id") != "EXP-SINGULAR-001":
        summary_mismatches.append("experiment_id")
    observed_control_ids = sorted(
        item["case_id"] for item in summary["candidate_control_disagreements"]
    )
    if observed_control_ids != sorted(control_disagreements):
        summary_mismatches.append("candidate_control_disagreements")
    observed_noneligible = sorted(
        (item["case_id"], item["variant"])
        for item in summary["noneligible_s4_promotions"]
    )
    if observed_noneligible != sorted(noneligible_promotions):
        summary_mismatches.append("noneligible_s4_promotions")
    if len(summary["metamorphic_disagreements"]) != len(metamorphic):
        summary_mismatches.append("metamorphic_disagreements")
    if len(summary["hard_budget_violations"]) != len(budget_violations):
        summary_mismatches.append("hard_budget_violations")
    if len(summary["evidence_failures"]) != len(evidence_failures):
        summary_mismatches.append("evidence_failures")
    passed = (
        not assessment_mismatches
        and not summary_mismatches
        and not mechanical_audit_failures
        and not work_accounting_failures
    )
    return {
        "assessment_mismatches": assessment_mismatches,
        "budget_violations": budget_violations,
        "candidate_control_disagreements": control_disagreements,
        "development_gate_passed": all(gates.values()),
        "evidence_failures": evidence_failures,
        "experiment_id": "EXP-SINGULAR-001",
        "independent_reconstruction_passed": passed,
        "metamorphic_disagreements": metamorphic,
        "mechanical_audit_failures": mechanical_audit_failures,
        "noneligible_promotions": noneligible_promotions,
        "reconstructed_advancement_gate": gates,
        "reconstructed_candidate_gain": str(gain),
        "reconstructed_variant_summaries": variant_summaries,
        "schema": "geotarget.singular-s4-independent-analysis/v1",
        "summary_mismatches": summary_mismatches,
        "work_accounting_failures": work_accounting_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-directory", type=Path, required=True)
    parser.add_argument("--experiment-directory", type=Path, required=True)
    args = parser.parse_args()
    result = args.result_directory.resolve()
    experiment = args.experiment_directory.resolve()
    raw_path = result / "raw.json"
    summary_path = result / "summary.json"
    environment_path = result / "environment.json"
    bindings_path = result / "result-bindings.json"
    manifest_path = experiment / "s4-development-input-manifest.json"
    gold_path = experiment / "s4-development-gold.json"
    input_freeze_path = experiment / "s4-input-freeze.json"
    implementation_freeze_path = experiment / "s4-implementation-freeze.json"
    checkpoint_manifest_path = result / "checkpoint-manifest.json"
    run_identity_path = result / "run-identity.json"
    warmup_path = result / "warmup.json"
    for path in (
        raw_path,
        summary_path,
        environment_path,
        bindings_path,
        manifest_path,
        gold_path,
        input_freeze_path,
        implementation_freeze_path,
        checkpoint_manifest_path,
        run_identity_path,
        warmup_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    bindings = load_json(bindings_path)
    expected = bindings["bindings"]
    observed_hashes = {
        "environment_sha256": sha256(environment_path),
        "checkpoint_manifest_sha256": sha256(checkpoint_manifest_path),
        "raw_sha256": sha256(raw_path),
        "report_sha256": sha256(result / "report.md"),
        "summary_sha256": sha256(summary_path),
    }
    for key, observed in observed_hashes.items():
        if expected[key] != observed:
            raise ValueError(f"result binding mismatch: {key}")
    environment = load_json(environment_path)
    manifest = load_json(manifest_path)
    gold = load_json(gold_path)
    input_freeze = load_json(input_freeze_path)
    implementation_freeze = load_json(implementation_freeze_path)
    checkpoint_manifest = load_json(checkpoint_manifest_path)
    run_identity = load_json(run_identity_path)
    warmup = load_json(warmup_path)
    if environment["input_manifest_sha256"] != sha256(manifest_path):
        raise ValueError("environment/input manifest mismatch")
    if manifest["gold_artifact_sha256"] != sha256(gold_path):
        raise ValueError("manifest/Gold hash mismatch")
    if gold.get("candidate_visible") is not False:
        raise ValueError("Gold visibility boundary mismatch")
    frozen_artifacts = input_freeze["artifacts"]
    manifest_key = (
        "research/experiments/EXP-SINGULAR-001/s4-development-input-manifest.json"
    )
    gold_key = "research/experiments/EXP-SINGULAR-001/s4-development-gold.json"
    if frozen_artifacts[manifest_key] != sha256(manifest_path):
        raise ValueError("input freeze/manifest mismatch")
    if frozen_artifacts[gold_key] != sha256(gold_path):
        raise ValueError("input freeze/Gold mismatch")
    implementation_sha = sha256(implementation_freeze_path)
    if environment["implementation_freeze_sha256"] != implementation_sha:
        raise ValueError("environment/implementation freeze mismatch")
    for key, expected_value in (
        ("checkpoint_manifest_sha256", sha256(checkpoint_manifest_path)),
        ("run_identity_sha256", sha256(run_identity_path)),
        ("warmup_sha256", sha256(warmup_path)),
        ("project_sha256", sha256(experiment / "Project.toml")),
        ("manifest_sha256", sha256(experiment / "Manifest.toml")),
    ):
        if environment[key] != expected_value:
            raise ValueError(f"environment binding mismatch: {key}")
    if environment["julia_threads"] != 1 or environment["blas_threads"] != 1:
        raise ValueError("environment thread mismatch")
    if bindings["implementation_freeze_sha256"] != implementation_sha:
        raise ValueError("result binding/implementation freeze mismatch")
    if bindings["checkpoint_manifest_sha256"] != sha256(checkpoint_manifest_path):
        raise ValueError("result binding/checkpoint manifest mismatch")
    if bindings["run_identity_sha256"] != sha256(run_identity_path):
        raise ValueError("result binding/run identity mismatch")
    if bindings["warmup_sha256"] != sha256(warmup_path):
        raise ValueError("result binding/warm-up mismatch")
    if implementation_freeze["input_freeze_sha256"] != sha256(input_freeze_path):
        raise ValueError("implementation/input freeze mismatch")
    repository = experiment.parents[2]
    for relative, expected_sha in implementation_freeze[
        "implementation_sources"
    ].items():
        source_path = repository / Path(relative)
        if not source_path.is_file() or sha256(source_path) != expected_sha:
            raise ValueError(f"implementation source mismatch: {relative}")
    if run_identity["schema"] != "geotarget.singular-s4-run-identity/v1":
        raise ValueError("run identity schema mismatch")
    if (
        run_identity["julia_version"] != "1.12.6"
        or run_identity["julia_threads"] != 1
        or run_identity["blas_threads"] != 1
    ):
        raise ValueError("run identity runtime mismatch")
    frozen_s4_options = run_identity["s4_options"]
    if (
        frozen_s4_options["precision_ladder"] != [128, 256]
        or frozen_s4_options["semantic_precision_bits"] != 256
        or frozen_s4_options["maximum_iterations"] != 64
        or frozen_s4_options["maximum_callbacks"] != 4096
        or frozen_s4_options["wall_seconds"] != 10.0
        or frozen_s4_options["independent_confirmation_count"] != 2
        or frozen_s4_options["error_reserve_multiplier"] != 16.0
        or frozen_s4_options["configuration_error_goal"] != 1e-10
        or frozen_s4_options["target_error_goal"] != 1e-12
        or frozen_s4_options["semantic_residual_tolerance"] != 1e-12
    ):
        raise ValueError("run identity S4 options mismatch")
    baseline_options = run_identity["baseline_options"]
    if (
        baseline_options["precision_ladder"] != [128, 256, 512, 1024]
        or baseline_options["maximum_iterations"] != 64
        or baseline_options["maximum_callbacks"] != 4096
        or baseline_options["wall_seconds"] != 10.0
    ):
        raise ValueError("run identity baseline options mismatch")
    if run_identity["project_sha256"] != sha256(experiment / "Project.toml"):
        raise ValueError("run identity Project mismatch")
    if run_identity["manifest_sha256"] != sha256(experiment / "Manifest.toml"):
        raise ValueError("run identity Manifest mismatch")
    if run_identity["runner_sha256"] != sha256(experiment / "run_s4_development.jl"):
        raise ValueError("run identity runner mismatch")
    if warmup["schema"] != "geotarget.singular-s4-warmup/v1" or warmup["measured"]:
        raise ValueError("warm-up contract mismatch")
    if len(warmup["fixtures"]) != 3 or any(
        fixture["statuses"]["S4-C2-NULLSPACE-TWO-STEP"] != "promoted"
        or fixture["statuses"]["S4-ANALYTIC-TWO-STEP-CONTROL"] != "promoted"
        for fixture in warmup["fixtures"]
    ):
        raise ValueError("warm-up mechanism mismatch")
    if checkpoint_manifest["schema"] != "geotarget.singular-s4-checkpoint-manifest/v1":
        raise ValueError("checkpoint manifest schema mismatch")
    if (
        len(checkpoint_manifest["checkpoints"]) != 36
        or checkpoint_manifest["row_count"] != 108
    ):
        raise ValueError("checkpoint manifest cardinality mismatch")
    checkpoint_rows: list[dict[str, Any]] = []
    for expected_index, entry in enumerate(checkpoint_manifest["checkpoints"], start=1):
        checkpoint_path = result / Path(entry["path"])
        if not checkpoint_path.is_file() or sha256(checkpoint_path) != entry["sha256"]:
            raise ValueError(f"checkpoint hash mismatch: {entry['path']}")
        if entry["case_index"] != expected_index:
            raise ValueError("checkpoint manifest order mismatch")
        expected_order = counterbalanced_variant_order(expected_index)
        if tuple(entry["variant_order"]) != expected_order:
            raise ValueError("checkpoint variant order mismatch")
        checkpoint = load_json(checkpoint_path)
        if tuple(checkpoint["variant_order"]) != expected_order:
            raise ValueError("checkpoint payload variant order mismatch")
        if checkpoint["run_identity_sha256"] != sha256(run_identity_path):
            raise ValueError("checkpoint runtime binding mismatch")
        if checkpoint["warmup_sha256"] != sha256(warmup_path):
            raise ValueError("checkpoint warm-up binding mismatch")
        if tuple(row["variant"] for row in checkpoint["rows"]) != expected_order:
            raise ValueError("checkpoint row order mismatch")
        checkpoint_rows.extend(checkpoint["rows"])
    raw_document = load_json(raw_path)
    if checkpoint_rows != raw_document["rows"]:
        raise ValueError("checkpoint/raw replay mismatch")
    with localcontext() as context:
        context.prec = 120
        analysis = analyze(
            raw_document,
            load_json(summary_path),
            manifest,
            gold,
        )
    analysis["source_bindings"] = {
        "checkpoint_manifest_sha256": sha256(checkpoint_manifest_path),
        "environment_sha256": observed_hashes["environment_sha256"],
        "gold_sha256": sha256(gold_path),
        "implementation_freeze_sha256": implementation_sha,
        "input_freeze_sha256": sha256(input_freeze_path),
        "input_manifest_sha256": sha256(manifest_path),
        "raw_sha256": observed_hashes["raw_sha256"],
        "run_identity_sha256": sha256(run_identity_path),
        "summary_sha256": observed_hashes["summary_sha256"],
        "warmup_sha256": sha256(warmup_path),
    }
    destination = result / "independent-analysis.json"
    destination.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if analysis["independent_reconstruction_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
