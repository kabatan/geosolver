#!/usr/bin/env python3.12
"""Serialization negative/large-integer/property D0, without corpus access."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import tempfile
from pathlib import Path

from lossless_transport import TransportError, decode_job, encode_job


HERE = Path(__file__).resolve().parent


def base_job(coefficients: list[object]) -> dict[str, object]:
    return {
        "truth_used": False,
        "post_process_used": False,
        "coordinate_descriptors": [
            {
                "coefficients_high_to_low": coefficients,
                "isolating_interval": {"left": "0", "right": "1", "multiplicity": 1},
            }
        ],
        "target_descriptor": {
            "minimal_polynomial_high_to_low": [1, -1],
            "isolating_interval": {"left": "0", "right": "1", "multiplicity": 1},
        },
        "nodes": [{"op": "coordinate", "index": 0}, {"op": "bool", "value": True}],
        "relation_roots": [0],
        "guard_roots": [1],
        "bound_roots": [],
        "answer_root": 0,
        "metadata": {"small_count": 17, "flag": True},
    }


def expect_rejected(name: str, job: dict[str, object]) -> dict[str, object]:
    try:
        encode_job(job)
    except TransportError as error:
        return {"name": name, "passed": True, "error": str(error)}
    return {"name": name, "passed": False, "error": "unexpected acceptance"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--julia-project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    rng = random.Random(0x4D534F4C5645)
    property_coefficients: list[int] = []
    for _ in range(256):
        bits = rng.randrange(0, 4097)
        value = rng.getrandbits(bits)
        if rng.randrange(2):
            value = -value
        property_coefficients.append(value)
    coefficients = [
        -(1 << 4096) + 1337,
        -(1 << 127),
        -(1 << 63),
        -1,
        0,
        1,
        1 << 63,
        (1 << 521) - 1,
        *property_coefficients,
    ]
    job = base_job(coefficients)
    encoded, attestation = encode_job(job)
    round_trip = decode_job(encoded)
    checks: list[dict[str, object]] = [
        {
            "name": "python_round_trip_264_values",
            "passed": round_trip == job,
        },
        {
            "name": "structural_integer_and_boolean_preserved",
            "passed": (
                encoded["nodes"][0]["index"] == 0
                and isinstance(encoded["nodes"][0]["index"], int)
                and encoded["metadata"]["flag"] is True
                and encoded["metadata"]["small_count"] == 17
            ),
        },
        {
            "name": "exact_integers_are_decimal_strings",
            "passed": all(
                isinstance(value, str)
                for value in encoded["coordinate_descriptors"][0]["coefficients_high_to_low"]
            ),
        },
    ]

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as stream:
        json.dump(encoded, stream, separators=(",", ":"), allow_nan=False)
        stream.flush()
        completed = subprocess.run(
            [
                "julia",
                "--compile=no",
                f"--project={arguments.julia_project}",
                "--startup-file=no",
                "--history-file=no",
                str(HERE / "transport_probe.jl"),
                stream.name,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20.0,
        )
    parsed = json.loads(completed.stdout) if completed.returncode == 0 else {}
    expected_texts = [str(value) for value in coefficients] + ["1", "-1"]
    checks.append(
        {
            "name": "json3_bigint_decimal_parse_property",
            "passed": completed.returncode == 0 and parsed.get("values") == expected_texts,
            "stderr": completed.stderr[-512:],
        }
    )

    invalid_jobs: list[tuple[str, dict[str, object]]] = []
    for name, bad in [
        ("boolean_coefficient", True),
        ("float_coefficient", 1.25),
        ("scientific_string", "-1.25e19"),
        ("leading_plus", "+2"),
        ("leading_zero", "01"),
        ("negative_zero", "-0"),
        ("whitespace", " 2"),
    ]:
        invalid_jobs.append((name, base_job([1, bad])))
    huge_control = base_job([1, -1])
    huge_control["metadata"]["unclassified"] = 1 << 200
    invalid_jobs.append(("unclassified_large_integer", huge_control))
    missing_coefficients = base_job([1, -1])
    missing_coefficients["coordinate_descriptors"][0]["coefficients_high_to_low"] = []
    invalid_jobs.append(("empty_exact_array", missing_coefficients))
    checks.extend(expect_rejected(name, candidate) for name, candidate in invalid_jobs)

    passed = sum(check.get("passed") is True for check in checks)
    result = {
        "schema_version": "geotarget.msolve-bigint-transport-serialization-d0/v1",
        "status": "PASS" if passed == len(checks) else "FAIL",
        "passed": passed,
        "total": len(checks),
        "property_seed": 0x4D534F4C5645,
        "property_integer_count": len(property_coefficients),
        "property_max_bits": max(abs(value).bit_length() for value in property_coefficients),
        "transport_attestation": attestation,
        "checks": checks,
        "truth_used": False,
        "formal_scorer_used": False,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "passed": passed, "total": len(checks)}))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
