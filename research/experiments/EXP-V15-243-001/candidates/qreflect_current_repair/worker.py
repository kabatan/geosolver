#!/usr/bin/env python3
"""Baseline-first repair for exact ``Reflect(QPoint, QPoint)`` replay.

The current exact outer remains the primary authority for at least 75% of
the endpoint allocation.  A bounded side replay is eligible only after that
exact closure reports the known missing QPoint/QPoint dispatch and the
untouched source has a statically closed direct point reflection.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Mapping


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
CURRENT_OUTER = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "exact_outer_decorator/worker.py"
)
CURRENT_OUTER_SHA256 = (
    "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7"
)
SIDE_WORKER = HERE / "fallback_worker.py"
BASELINE_FRACTION = 0.75
SIDE_FRACTION = 0.25


class IntegrationError(RuntimeError):
    pass


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


if _sha256(CURRENT_OUTER) != CURRENT_OUTER_SHA256:
    raise IntegrationError("current exact outer SHA-256 changed")
OUTER = _load("qreflect_repair_current_exact_outer", CURRENT_OUTER)
BASE = OUTER.BASE
RESOURCE = OUTER.RESOURCE
BASELINE = BASE._run_hp_candidate
BASELINE_CAPTURE_COUNT = 1


def _closed_scalar(node: ast.AST, variables: frozenset[str]) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(
            node.value, bool
        )
    if isinstance(node, ast.Name):
        return node.id in variables
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _closed_scalar(node.operand, variables)
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
    ):
        return _closed_scalar(node.left, variables) and _closed_scalar(
            node.right, variables
        )
    return False


def _direct_point_reflect_count(document: object) -> int:
    """Count only sequential ``Reflect(point, center_point)`` constructions.

    Any Reflect selector, container, keyword, unknown/mixed type, nested call,
    or wrong arity makes the source ineligible.  This classifier never reads
    a target value, answer value, case ID, family, or outcome.
    """

    if not isinstance(document, Mapping):
        return 0
    variables_value = document.get("variables")
    names = variables_value.get("names") if isinstance(variables_value, Mapping) else None
    construction = document.get("construction")
    if (
        not isinstance(names, list)
        or not all(isinstance(name, str) for name in names)
        or not isinstance(construction, list)
    ):
        return 0
    variables = frozenset(names)
    types: dict[str, str] = {}
    reflect_count = 0
    for record in construction:
        if (
            not isinstance(record, Mapping)
            or not isinstance(record.get("name"), str)
            or not isinstance(record.get("expr"), str)
            or record["name"] in types
        ):
            return 0
        try:
            expression = ast.parse(record["expr"], mode="eval").body
        except (SyntaxError, ValueError):
            return 0
        reflect_nodes = [
            node
            for node in ast.walk(expression)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Reflect"
        ]
        top_is_reflect = bool(
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id == "Reflect"
        )
        if reflect_nodes and (not top_is_reflect or len(reflect_nodes) != 1):
            return 0
        if not isinstance(expression, ast.Call) or not isinstance(
            expression.func, ast.Name
        ):
            types[record["name"]] = "unknown"
            continue
        call_name = expression.func.id
        if call_name == "Point":
            if (
                len(expression.args) == 2
                and not expression.keywords
                and all(_closed_scalar(item, variables) for item in expression.args)
            ):
                types[record["name"]] = "point"
            else:
                types[record["name"]] = "unknown"
        elif call_name == "Line":
            if (
                len(expression.args) == 2
                and not expression.keywords
                and all(isinstance(item, ast.Name) for item in expression.args)
                and all(types.get(item.id) == "point" for item in expression.args)
            ) or (
                len(expression.args) == 3
                and not expression.keywords
                and all(_closed_scalar(item, variables) for item in expression.args)
            ):
                types[record["name"]] = "line"
            else:
                types[record["name"]] = "unknown"
        elif call_name == "Reflect":
            direct_names = (
                len(expression.args) == 2
                and not expression.keywords
                and all(isinstance(item, ast.Name) for item in expression.args)
            )
            if not direct_names:
                return 0
            first, second = expression.args
            if types.get(first.id) != "point" or types.get(second.id) != "point":
                return 0
            types[record["name"]] = "point"
            reflect_count += 1
        else:
            types[record["name"]] = "unknown"
    return reflect_count


def _source_activation(kwargs: Mapping[str, object]) -> int:
    source = Path(kwargs["source"])
    try:
        payload = source.read_bytes()
        if hashlib.sha256(payload).hexdigest() != str(kwargs["source_sha256"]):
            return 0
        document = json.loads(payload)
    except (OSError, json.JSONDecodeError):
        return 0
    return _direct_point_reflect_count(document)


def _baseline_missing_dispatch(kwargs: Mapping[str, object]) -> bool:
    artifact = Path(kwargs["output"]) / "exact-coordinate-fallback/RESULT.json"
    try:
        value = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(value, Mapping):
        return False
    failure = str(value.get("failure", ""))
    lowered = failure.lower()
    return bool(
        value.get("schema_version")
        == "geotarget.v15-243-exact-coordinate-fallback/v1"
        and value.get("source_sha256") == str(kwargs["source_sha256"])
        and value.get("endpoint_float64_sha256")
        == str(kwargs["candidate"].endpoint_sha256)
        and value.get("status") == "EXACT_COORDINATE_FALLBACK_REJECTED"
        and value.get("authority_pass") is False
        and "qreflect" in lowered
        and "qpoint" in lowered
        and ("methoderror" in lowered or "no method matching" in lowered)
    )


def _command(kwargs: Mapping[str, object], artifact: Path, side_seconds: float):
    candidate = kwargs["candidate"]
    return [
        "taskset",
        "-c",
        str(int(kwargs["cpu"])),
        str(BASE.PYTHON),
        str(SIDE_WORKER),
        "--source",
        str(Path(kwargs["source"]).resolve()),
        "--source-sha256",
        str(kwargs["source_sha256"]),
        "--endpoint",
        json.dumps(candidate.endpoint, separators=(",", ":"), allow_nan=False),
        "--endpoint-sha256",
        str(candidate.endpoint_sha256),
        "--timeout-seconds",
        str(max(0.5, side_seconds - 0.5)),
        "--output",
        str(artifact.resolve()),
    ]


def _run_side(kwargs: Mapping[str, object], side_seconds: float, direct_count: int):
    cpu = int(kwargs["cpu"])
    root = Path(kwargs["output"]) / "qreflect-point-repair"
    artifact = root / "RESULT.json"
    artifact.unlink(missing_ok=True)
    guarded = None
    try:
        with RESOURCE.adapter.per_core_lease(
            cpu,
            wait_seconds=min(
                RESOURCE.adapter.DEFAULT_POLICY.maximum_core_lease_wait_seconds,
                max(0.0, side_seconds - 1.0),
            ),
        ):
            root.mkdir(parents=True, exist_ok=True)
            guarded = BASE.run_guarded(
                _command(kwargs, artifact, side_seconds),
                limits=BASE.Limits(
                    timeout_seconds=side_seconds,
                    rss_bytes=768 * 1024**2,
                    address_space_bytes=3072 * 1024**2,
                    data_bytes=2048 * 1024**2,
                    output_bytes=1024**2,
                    tail_bytes=16 * 1024,
                ),
                environment=BASE.THREAD_ENVIRONMENT,
                cwd=RUNTIME_ROOT,
                status_path=root / "process-status.json",
            )
    except RESOURCE.adapter.LeaseUnavailable:
        return None, {"status": "LOCK_BUSY_DEFERRED", "authority_pass": False}
    fallback = None
    try:
        loaded = json.loads(artifact.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            fallback = loaded
    except (OSError, json.JSONDecodeError):
        pass
    descriptor = OUTER._consume_fallback(
        fallback=fallback,
        guarded=guarded,
        source=Path(kwargs["source"]),
        source_sha256=str(kwargs["source_sha256"]),
        candidate=kwargs["candidate"],
    )
    containment = fallback.get("containment") if isinstance(fallback, Mapping) else None
    accepted = bool(
        descriptor is not None
        and direct_count > 0
        and isinstance(containment, Mapping)
        and containment.get("same_process_group") is True
        and containment.get("pdeathsig") == 9
        and containment.get("cpu_affinity") == [cpu]
    )
    evidence = {
        "status": "TARGET_AUTHORITY_READY" if accepted else "SIDE_REJECTED",
        "authority_pass": accepted,
        "allocated_seconds": side_seconds,
        "direct_point_reflect_count": direct_count,
        "result_sha256": _sha256(artifact) if artifact.is_file() else None,
        "process": guarded.to_dict() if guarded is not None else None,
        "containment": dict(containment) if isinstance(containment, Mapping) else None,
        "canonical_source_guard_branch_raw_target_minpoly_ordinal_isolator_numeric_parity": (
            descriptor is not None
        ),
        "truth_used": False,
        "target_set_completeness_claim": False,
    }
    return descriptor if accepted else None, evidence


def _run(**kwargs):
    total = float(kwargs["timeout_seconds"])
    started = time.monotonic()
    baseline_kwargs = dict(kwargs)
    baseline_kwargs["timeout_seconds"] = max(0.5, total * BASELINE_FRACTION)
    baseline = BASELINE(**baseline_kwargs)
    if OUTER._ordinary_resource_busy(baseline) or OUTER._ordinary_ready(baseline):
        return baseline
    endpoint = getattr(kwargs["candidate"], "endpoint", None)
    if not isinstance(endpoint, (list, tuple)) or len(endpoint) == 0:
        return baseline
    direct_count = _source_activation(kwargs)
    if direct_count <= 0 or not _baseline_missing_dispatch(kwargs):
        return baseline
    side_seconds = min(total * SIDE_FRACTION, total - (time.monotonic() - started))
    if side_seconds < 0.5:
        return baseline
    try:
        descriptor, evidence = _run_side(kwargs, side_seconds, direct_count)
    except Exception:
        return baseline
    if descriptor is None:
        return baseline
    candidate = kwargs["candidate"]
    return {
        "attempt_kind": "EXACT_QREFLECT_POINT_DISPATCH_REPAIR",
        "endpoint_float64_sha256": candidate.endpoint_sha256,
        "residual_inf": candidate.residual_inf,
        "provisional_target": candidate.provisional_target,
        "cluster_ordinal": candidate.cluster_ordinal,
        "cluster_rank": candidate.cluster_rank,
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": descriptor,
        "baseline_exact_outer_result": baseline,
        "qreflect_point_repair": evidence,
        "baseline_minimum_fraction": BASELINE_FRACTION,
        "side_maximum_fraction": SIDE_FRACTION,
        "case_family_truth_target_count_routing": False,
    }


if getattr(BASE, "_qreflect_point_repair_installed", False):
    raise IntegrationError("qreflect point repair installed twice")
BASE._run_hp_candidate = _run
BASE._qreflect_point_repair_installed = True


def main() -> None:
    OUTER.SCHEDULER_MODULE.main()


if __name__ == "__main__":
    main()
