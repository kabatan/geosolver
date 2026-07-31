from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import sympy as sp

from exact_connector import linear_target_descriptor, rational_coordinate_descriptor


HERE = Path(__file__).resolve().parent


def test_sources_parse() -> None:
    for name in (
        "candidate.py", "exact_connector.py", "generated_d0.py", "run_d0.py", "run_real_gate.py"
    ):
        ast.parse((HERE / name).read_text(encoding="utf-8"), filename=name)


def test_no_cross_prime_product_or_float_coordinate_roundtrip() -> None:
    source = (HERE / "candidate.py").read_text(encoding="utf-8")
    assert "itertools.product" not in source
    assert "_crt" not in source
    assert '"cross_prime_cartesian_product": False' in source
    assert '"crt_used": False' in source
    assert "float(" not in source


def test_rational_descriptor_is_linear_point_isolator() -> None:
    value = rational_coordinate_descriptor(sp.Rational(-2, 3))
    assert value["coefficients_high_to_low"] == [3, 2]
    interval = value["polynomial_metadata"]["isolating_interval"]
    assert interval == {
        "left": "-2/3", "right": "-2/3", "multiplicity": 1, "real_root_index": 0
    }
    target = linear_target_descriptor([-6, 4])
    assert target["coefficients_high_to_low"] == [3, -2]
    assert target["polynomial_metadata"]["isolating_interval"]["left"] == "2/3"


def test_arm_is_four_field_proposal_only_entrypoint() -> None:
    value = json.loads((HERE / "arm.json").read_text(encoding="utf-8"))
    assert set(value) == {"id", "base_commit", "entrypoint", "mechanism_hash"}
    assert value["entrypoint"] == "candidate.py"
    assert value["mechanism_hash"] == hashlib.sha256((HERE / "candidate.py").read_bytes()).hexdigest()
