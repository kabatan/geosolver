from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import prefix
import policy
import runtime
import scaling


def test_runtime_authority_is_hash_bound_and_has_no_forbidden_dependency():
    assert hashlib.sha256(runtime.AUTHORITY_PATH.read_bytes()).hexdigest() == (
        runtime.AUTHORITY_SHA256
    )
    tree = ast.parse(runtime.AUTHORITY_PATH.read_text(encoding="utf-8"))
    forbidden = "infer_" + "problem_bounds"
    forbidden_fields = {"legacy_" + "lower", "legacy_" + "upper"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert forbidden not in ast.unparse(node)
        if isinstance(node, ast.Call):
            assert forbidden not in ast.unparse(node.func)
        if isinstance(node, ast.Attribute):
            assert node.attr not in forbidden_fields


def test_missing_bounds_remain_infinite_and_explicit_bounds_are_unchanged():
    lower, upper = runtime.source_bounds({}, 3)
    assert np.all(np.isneginf(lower))
    assert np.all(np.isposinf(upper))
    explicit = {"bounds": [[-2, 3], [4, 9]]}
    lower, upper = runtime.source_bounds(explicit, 2)
    assert np.array_equal(lower, [-2.0, 4.0])
    assert np.array_equal(upper, [3.0, 9.0])


def test_prefix_is_deterministic_full_support_and_prefix_insured():
    lower = np.full(4, -np.inf)
    upper = np.full(4, np.inf)
    first = prefix.generate_prefix(lower, upper, count=31, seed=17)
    second = prefix.generate_prefix(lower, upper, count=31, seed=17)
    assert first.sha256 == second.sha256
    assert all(
        left.tobytes() == right.tobytes()
        for left, right in zip(first.points, second.points, strict=True)
    )
    assert all(np.all(np.isfinite(point)) for point in first.points)
    assert set(first.sources) == {
        "counter_product_cauchy",
        "scrambled_sobol_rational",
    }
    for length in range(1, len(first.points) + 1):
        insured = first.sources[:length].count("counter_product_cauchy")
        assert 4 * insured >= length
    assert prefix.frozen_configuration()["finite_search_envelope"] is False
    assert prefix.frozen_configuration()["proposal_coordinate_clipping"] is False


def test_prefix_maps_only_explicitly_bounded_axes_to_source_interval():
    lower = np.asarray([-3.0, -np.inf])
    upper = np.asarray([7.0, np.inf])
    result = prefix.generate_prefix(lower, upper, count=64, seed=5)
    assert all(-3.0 <= point[0] <= 7.0 for point in result.points)
    assert max(abs(float(point[1])) for point in result.points) > 10.0


def test_per_start_scaling_and_bounded_column_equilibration():
    point = np.asarray([0.0, -2.0, 10.0])
    assert np.array_equal(scaling.base_scales(point), [1.0, 2.0, 10.0])
    equilibrated = scaling.equilibrate_columns(
        np.ones(2), np.asarray([[100.0, 0.0], [0.0, 1.0]])
    )
    assert np.allclose(equilibrated, [0.25, 4.0])
    config = scaling.frozen_configuration()
    assert config["jacobian_column_equilibration"] is False
    assert config["scales_are_search_bounds"] is False


def test_policy_packet_exposes_only_starts_and_local_affine_scaling():
    document = {"variables": {"names": ["x", "y"]}, "bounds": None}
    packet = policy.materialize_policy(
        document, source_sha256="ab" * 32, starts=8, seed=3
    )
    assert all(
        origin.tobytes() == point.tobytes()
        for origin, point in zip(packet.local_origins, packet.points, strict=True)
    )
    assert all(
        np.array_equal(scale, np.maximum(1.0, np.abs(point)))
        for scale, point in zip(packet.local_scales, packet.points, strict=True)
    )
    record = policy.packet_record(packet)
    assert record["configuration"]["non_source_bounds_or_envelope"] is False
    assert record["configuration"]["case_family_truth_target_count_routing"] is False


def test_real_document_compile_and_proposal_generation_charge_no_callbacks():
    manifest_path = ROOT / "research/corpora/real-geometry-61/development-v3/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    binding = manifest["cases"][0]["dsl"]
    case_path = (manifest_path.parent / binding["path"]).resolve()
    payload = case_path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == binding["sha256"]
    document = json.loads(payload)
    case, budget, _evaluator = runtime.build_source_case(
        document, callback_cap=64, deadline=time.monotonic() + 5.0
    )
    proposals = prefix.generate_prefix(case.lower, case.upper, count=16, seed=0)
    assert budget.callbacks == 0
    assert np.all(case.origin == 0.0)
    assert np.all(case.scales == 1.0)
    assert len(proposals.points) == 16
    assert case_path.read_bytes() == payload
