from __future__ import annotations

from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

import pytest


HERE = Path(__file__).resolve().parent
PRIVATE = HERE / "private_candidate.py"
FALLBACK = HERE / "private_fallback_worker.py"
WORKER = HERE / "worker.py"
ARM = HERE / "arm.json"
CONTAINED = HERE / "contained_lifecycle.py"
JULIA = "/home/kabatan/.juliaup/bin/julia"
JULIA_PROJECT = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-REAL61-002/target_elimination"
)


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def private():
    return _load(f"reflect_private_test_{uuid.uuid4().hex}", PRIVATE)


def _descriptor(value: Fraction | int) -> dict[str, object]:
    value = Fraction(value)
    return {
        "coefficients_high_to_low": [str(value.denominator), str(-value.numerator)],
        "isolating_interval": {
            "left": str(value),
            "right": str(value),
            "multiplicity": 1,
            "real_root_index": 0,
        },
    }


def _rational(nodes: list[dict[str, object]], value: Fraction | int) -> int:
    nodes.append({"op": "rational", "value": str(Fraction(value))})
    return len(nodes) - 1


def _call(
    nodes: list[dict[str, object]], name: str, *arguments: int
) -> int:
    nodes.append(
        {"op": "call", "name": name, "args": list(arguments), "kwargs": {}}
    )
    return len(nodes) - 1


def _point(nodes: list[dict[str, object]], x: Fraction | int, y: Fraction | int) -> int:
    return _call(nodes, "Point", _rational(nodes, x), _rational(nodes, y))


def _point_reflect_job(
    point: tuple[Fraction | int, Fraction | int],
    center: tuple[Fraction | int, Fraction | int],
    *,
    coordinate: str = "CoordinateX",
    target: Fraction | int | None = None,
) -> dict[str, object]:
    nodes: list[dict[str, object]] = []
    point_node = _point(nodes, *point)
    center_node = _point(nodes, *center)
    reflected = _call(nodes, "Reflect", point_node, center_node)
    answer = _call(nodes, coordinate, reflected)
    axis = 0 if coordinate == "CoordinateX" else 1
    exact_target = Fraction(2) * Fraction(center[axis]) - Fraction(point[axis])
    return {
        "truth_used": False,
        "post_process_used": False,
        "coordinate_descriptors": [],
        "target_descriptor": _descriptor(exact_target if target is None else target),
        "nodes": nodes,
        "relation_roots": [],
        "guard_roots": [],
        "bound_roots": [],
        "answer_root": answer,
    }


def _wrong_type_job() -> dict[str, object]:
    nodes: list[dict[str, object]] = []
    point = _point(nodes, 1, 2)
    scalar = _rational(nodes, 3)
    reflected = _call(nodes, "Reflect", point, scalar)
    answer = _call(nodes, "CoordinateX", reflected)
    return {
        "truth_used": False,
        "post_process_used": False,
        "coordinate_descriptors": [],
        "target_descriptor": _descriptor(5),
        "nodes": nodes,
        "relation_roots": [],
        "guard_roots": [],
        "bound_roots": [],
        "answer_root": answer,
    }


def _line_reflect_job() -> dict[str, object]:
    nodes: list[dict[str, object]] = []
    point = _point(nodes, 3, 4)
    start = _point(nodes, 0, 0)
    finish = _point(nodes, 1, 0)
    line = _call(nodes, "Line", start, finish)
    reflected = _call(nodes, "Reflect", point, line)
    answer = _call(nodes, "CoordinateY", reflected)
    return {
        "truth_used": False,
        "post_process_used": False,
        "coordinate_descriptors": [],
        "target_descriptor": _descriptor(-4),
        "nodes": nodes,
        "relation_roots": [],
        "guard_roots": [],
        "bound_roots": [],
        "answer_root": answer,
    }


def _run_julia(source: str, job: dict[str, object]) -> dict[str, object]:
    environment = os.environ.copy()
    environment.update(
        {
            "JULIA_NUM_THREADS": "1",
            "JULIA_NUM_GC_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        }
    )
    with tempfile.TemporaryDirectory(prefix="reflect-exact-d0-") as directory:
        root = Path(directory)
        worker = root / "worker.jl"
        job_path = root / "job.json"
        worker.write_text(source, encoding="utf-8")
        job_path.write_text(json.dumps(job), encoding="utf-8")
        completed = subprocess.run(
            [
                JULIA,
                "--compile=no",
                f"--project={JULIA_PROJECT}",
                "--startup-file=no",
                "--history-file=no",
                str(worker),
                str(job_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
            env=environment,
        )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _accepted(result: dict[str, object]) -> None:
    assert result["status"] == "EXACT_REPLAY_ACCEPTED"
    assert result["source_raw_answer_exact"] is True
    assert result["target_link_exact"] is True
    assert result["root_ordinal_attestation_complete"] is True
    assert result["maximum_intermediate_qqbar_degree"] <= 8


def test_only_point_overload_changes_frozen_extended_source(private) -> None:
    patched = private.extended_worker_source()
    original = private._ORIGINAL_EXTENDED_WORKER_SOURCE()
    assert patched.count("function qreflect(value::QPoint, center::QPoint)") == 1
    assert private.remove_point_reflect_overload(patched) == original
    assert private.closure_manifest()[
        "other_extended_worker_bytes_identical_after_overload_removal"
    ] is True


def test_typed_numeric_semantics_and_argument_order() -> None:
    geosolver_source = Path(
        "/home/kabatan/work/solver-experiment-runtime/geosolver/src"
    )
    sys.path.insert(0, str(geosolver_source))
    from geosolver.geometry.entities.base import Point
    from geosolver.geometry.operations.transforms import Reflect

    point = Point(1, 2)
    center = Point(4, 7)
    forward = Reflect(point, center)
    reverse = Reflect(center, point)
    assert (forward.x, forward.y) == (7, 12)
    assert (reverse.x, reverse.y) == (-2, -3)


def test_full_candidate_compiles_and_replays_point_reflection_source(private) -> None:
    document = {
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "P", "expr": "Point(x, y)"},
            {"name": "C", "expr": "Point(4, 7)"},
            {"name": "R", "expr": "Reflect(P, C)"},
        ],
        "constraints": [
            {"def": "x", "value": 1},
            {"def": "y", "value": 2},
        ],
        "guards": ["AssumeGt(R.x, P.x)"],
        "answer": "R.x",
    }
    result = private.certify_exact_coordinate_witness(
        document,
        ["1", "2"],
        ["1", "2"],
        "7",
        "7",
        timeout_seconds=30.0,
    )
    assert result["status"] == "EXACT_TARGET_AUTHORITY_READY", result
    assert result["source_constraints_exact"] == 2
    assert result["source_guards_exact"] == 1
    assert result["source_raw_answer_exact"] is True
    assert result["target_link_exact"] is True


@pytest.mark.parametrize(
    ("point", "center", "coordinate"),
    [
        ((1, 2), (4, 7), "CoordinateX"),
        ((Fraction(1, 3), -2), (Fraction(5, 2), 3), "CoordinateY"),
        ((-11, Fraction(7, 5)), (2, Fraction(-3, 4)), "CoordinateX"),
    ],
)
def test_positive_exact_point_reflection(private, point, center, coordinate) -> None:
    result = _run_julia(
        private.extended_worker_source(),
        _point_reflect_job(point, center, coordinate=coordinate),
    )
    _accepted(result)
    assert result["operation_counts"]["call"] == 4


def test_argument_order_is_reflected_point_then_center(private) -> None:
    source = private.extended_worker_source()
    forward = _run_julia(source, _point_reflect_job((1, 2), (4, 7)))
    reverse = _run_julia(source, _point_reflect_job((4, 7), (1, 2)))
    _accepted(forward)
    _accepted(reverse)
    wrong_order_target = _run_julia(
        source,
        _point_reflect_job((4, 7), (1, 2), target=7),
    )
    assert wrong_order_target["status"] == "EXACT_REPLAY_REJECTED"


@pytest.mark.parametrize(
    ("point", "center"),
    [
        ((8, -3), (13, 5)),  # translation
        ((-2, 1), (-7, 4)),  # reflection across the y axis
        ((-3, 2), (-5, -7)),  # 90-degree rotation
        ((5, 5), (13, 11)),  # invertible affine shear/scale image
    ],
)
def test_affine_rotation_reflection_metamorphic(private, point, center) -> None:
    _accepted(
        _run_julia(
            private.extended_worker_source(),
            _point_reflect_job(point, center, coordinate="CoordinateY"),
        )
    )


def test_wrong_target_and_wrong_type_fail_closed(private) -> None:
    source = private.extended_worker_source()
    wrong_target = _run_julia(source, _point_reflect_job((1, 2), (4, 7), target=8))
    wrong_type = _run_julia(source, _wrong_type_job())
    assert wrong_target["status"] == "EXACT_REPLAY_REJECTED"
    assert wrong_type["status"] == "EXACT_REPLAY_REJECTED"
    assert "qreflect" in str(wrong_type["error"])


def test_existing_line_reflection_result_is_exactly_identical(private) -> None:
    original = _run_julia(private._ORIGINAL_EXTENDED_WORKER_SOURCE(), _line_reflect_job())
    patched = _run_julia(private.extended_worker_source(), _line_reflect_job())
    assert patched == original
    _accepted(patched)


def test_private_fallback_binds_only_private_certifier() -> None:
    fallback = _load(f"reflect_fallback_test_{uuid.uuid4().hex}", FALLBACK)
    assert fallback.ORIGINAL.certify_exact_coordinate_witness is fallback.PRIVATE.certify_exact_coordinate_witness
    assert fallback.verify_dependencies()


def test_candidate_private_formal_guard_is_quiet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sys.path.insert(0, "/home/kabatan/work/solver-experiment-runtime/solver")
    lifecycle = _load(f"reflect_containment_test_{uuid.uuid4().hex}", CONTAINED)
    safe = lifecycle.DEADLINE.same_group.SAFE
    limits = safe.Limits(
        timeout_seconds=4.0,
        rss_bytes=128 * 1024 * 1024,
        address_space_bytes=1024 * 1024 * 1024,
        data_bytes=512 * 1024 * 1024,
        output_bytes=128 * 1024,
        tail_bytes=16 * 1024,
        poll_seconds=0.01,
        terminate_grace_seconds=0.2,
    )
    monkeypatch.setenv(
        lifecycle.FORMAL_DEADLINE_ENV,
        str(time.monotonic() + 6.0),
    )
    child = """
import json
import os
import subprocess
import sys
import contained_lifecycle
from research.infrastructure.memory_safety import safe_subprocess

grandchild = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(0.20)"]
)
print(json.dumps({
    "root_pid": os.getpid(),
    "grandchild_pid": grandchild.pid,
    "sitecustomize_propagated": (
        safe_subprocess.run_guarded is contained_lifecycle.contained_run_guarded
    ),
}), flush=True)
grandchild.wait()
"""
    environment = os.environ.copy()
    environment.update(
        {
            lifecycle.ACTIVATION_ENV: "1",
            "PYTHONPATH": lifecycle._child_python_path(),
        }
    )
    result = lifecycle.contained_run_guarded(
        [sys.executable, "-c", child],
        limits=limits,
        environment=environment,
        status_path=tmp_path / "containment-status.json",
    )
    assert result.classification == "SUCCESS", result
    assert result.accepted_output is True
    assert result.containment_breach is False
    assert result.descendant_leak is False
    assert result.descendants_observed >= 1
    payload = json.loads(result.stdout_tail.strip().splitlines()[-1])
    assert payload["sitecustomize_propagated"] is True
    for _ in range(20):
        if all(
            not Path(f"/proc/{payload[name]}").exists()
            for name in ("root_pid", "grandchild_pid")
        ):
            break
        time.sleep(0.01)
    assert all(
        not Path(f"/proc/{payload[name]}").exists()
        for name in ("root_pid", "grandchild_pid")
    )
    status = json.loads((tmp_path / "containment-status.json").read_text())
    assert status["classification"] == "SUCCESS"
    assert status["containment_breach"] is False
    assert status["descendant_leak"] is False


def test_archive_binding_and_truth_blind_plan(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER", raising=False)
    monkeypatch.delenv("GEOTARGET_EXACT_OUTER_MODE", raising=False)
    module = _load(f"reflect_archive_test_{uuid.uuid4().hex}", WORKER)
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "task": "solve",
                "variables": {"names": ["x"]},
                "constructions": [],
                "constraints": ["x == 0"],
                "guards": [],
                "answer": "x",
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    plan = module.BASE._plan(
        source=source,
        source_sha256=digest,
        total_seconds=30.0,
        search_seconds=20.0,
        starts=1,
        callbacks_per_start=2,
        aggregate_callback_cap=2,
        seed=0,
        cpu=15,
        output=tmp_path / "plan",
    )
    assert module.OUTER.EXACT_CANDIDATE == PRIVATE
    assert module.OUTER.EXACT_WORKER == FALLBACK
    assert module.BASE._run_hp_candidate is module.OUTER._run_exact_outer
    assert plan["exact_reflect_point_opcode"] == "qreflect(::QPoint, ::QPoint)"
    assert plan["exact_reflect_point_branch_or_guard_added"] is False
    assert plan["case_family_truth_target_count_or_outcome_routing"] is False
    assert plan["exact_coordinate_fallback"]["closure"]["maximum_recognition_degree"] == 8


def test_arm_mechanism_hash_is_entrypoint_hash() -> None:
    arm = json.loads(ARM.read_text(encoding="utf-8"))
    assert arm["entrypoint"] == "worker.py"
    assert arm["mechanism_hash"] == hashlib.sha256(WORKER.read_bytes()).hexdigest()
