#!/usr/bin/env python3
"""One-refinement exact-coordinate worker with two narrow opcode repairs.

This disposable worker is the frozen sector exact-coordinate worker with one
additional exact ``Reflect(QPoint, QPoint)`` dispatch.  It does not route on a
case identity or on a numeric endpoint.  The sector repair remains
failure-only and internally reserves 75% of exact replay time for its generic
QQBar replay.  The qreflect repair is a type-exact Julia method, so it activates
only when the canonical DAG reaches that formerly missing dispatch.

The ordinary endpoint, numeric refinement, source replay, root ordinal
attestation, and exact-outer authority consumer are unchanged.  No route
claims target-set completeness.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from math import gcd
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any, Iterator, Mapping, Sequence


HERE = Path(__file__).resolve().parent
PYTHON = Path("/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python")
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
SECTOR_ROOT = Path(
    "/home/kabatan/work/solver-wt/sector-certified-integer-angle-relation/research/"
    "experiments/EXP-V15-243-001/candidates/typed_semantic_equal_qbar_pi_affine_v1"
)
QREFLECT_ROOT = Path(
    "/home/kabatan/work/solver-wt/qreflect-current-repair/research/experiments/"
    "EXP-V15-243-001/candidates/qreflect_current_repair"
)
SECTOR_WORKER = SECTOR_ROOT / "modified_fallback_worker.py"
SECTOR_CANDIDATE = SECTOR_ROOT / "current_exact_candidate.py"
SECTOR_CONNECTOR = SECTOR_ROOT / "sector_angle_connector.py"
SECTOR_TYPED_CONNECTOR = SECTOR_ROOT / "typed_replay_connector.py"
SECTOR_SCANNER = SECTOR_ROOT / "scanner.py"
SECTOR_DAG = SECTOR_ROOT / "current_dag_compile.py"
SECTOR_QQBAR = SECTOR_ROOT / "current_qqbar_worker.jl"
QREFLECT_REFERENCE_QQBAR = QREFLECT_ROOT / "qqbar_worker.jl"
AUTHORITY_BOUNDARY = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "exact_outer_decorator/authority_boundary.py"
)
REFINER = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-001/refine_proposals_worker.py"
)
PYTHON_ENV = RUNTIME_ROOT / "python/.venv"
SITE_PACKAGES = PYTHON_ENV / "lib/python3.12/site-packages"
SCHEMA = "geotarget.v15-243-exact-coordinate-fallback/v1"
PORTFOLIO_SCHEMA = "geotarget.categorical-exact-coordinate-union/v2"
MAX_SOURCE_BYTES = 4 * 1024 * 1024

FROZEN_DEPENDENCIES = {
    PYTHON: "ccc93c55c24bb92866cc2f9eff61b124abf5d1ee6c8da0ef9b5eed4d78a21f07",
    SECTOR_WORKER: "5641b5c49f015034214d0c3be5e7b53ae31d2ccef3c71f6163dd8d8db5a968fb",
    SECTOR_CANDIDATE: "cc454bae4927d2c4b2b079e77e31843217bbfde403ea9138a40c7d6b0b4da5da",
    SECTOR_CONNECTOR: "851df840c2f52a99e1664a74060df44ff21ac0406d0a82ec2200fa5d5a90befc",
    SECTOR_TYPED_CONNECTOR: "2259ceaa3d5bdb3718dad3ca7179fcfd894711f29ae7060d2d87dbe4355faf3b",
    SECTOR_SCANNER: "4636f050dd5c5aed5c282b0bdca43d7db170f06d504ee623c7b88613ca453c6b",
    SECTOR_DAG: "9b83181004a8ea2ea73f2974129e37ce252f7d352937b9f8b601b39eddf03d18",
    SECTOR_QQBAR: "3ac6415600da77f8748a11d15fa47eb3dcb9f8deada375388fc762a155df0b4a",
    QREFLECT_REFERENCE_QQBAR: "482b093772cec9c6f2d9cde1bbd3dd6c664f552a89fda70a12550928799b0a76",
    REFINER: "14a107893f6db1b9ec113c28653a40b3817f274865b0fabc64e2a13702bdc7b3",
    AUTHORITY_BOUNDARY: "a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9",
    PYTHON_ENV / "pyvenv.cfg": "df9924cf29c7574204083500a8f062501ccaa42ab95aa437ca74c982e83fafee",
    SITE_PACKAGES / "numpy-2.5.1.dist-info/METADATA": "6ae45122ee97050e48849438320430d05f01814f72e66e69cbeed027d2c6a1e8",
    SITE_PACKAGES / "scipy-1.18.0.dist-info/METADATA": "157bd150af3af33b40ec61489be8153752b269fb10c4b45b8cea5104f3235420",
    SITE_PACKAGES / "mpmath-1.3.0.dist-info/METADATA": "44b66ea444b9c0d19ae94815d356bf047ae6b680c19268b5c265687cd6a81406",
    SITE_PACKAGES / "sympy-1.14.0.dist-info/METADATA": "b756c2fbfd5be05ac5bdb0ebca61f55618f30f633ed92d88a5687429313a7595",
    SITE_PACKAGES / "numpy/__init__.py": "09295a80660f17925ae23765ce8cbd7ff7ceae968d5f2f89349f1cb74c0b9e11",
    SITE_PACKAGES / "scipy/__init__.py": "39ccae300a4739cc53719bd3b39ce3f8f66e736c6eb672006e338a4c5cc3dc76",
    SITE_PACKAGES / "mpmath/__init__.py": "b241584d2c1fc0304b0a1015ea923749d7b0800411dd406dcab7c82bf25d9fe8",
    SITE_PACKAGES / "sympy/__init__.py": "4e9476348ba105feab28d82f5bcf6cdba2e3e84de6e059bbfe7a13728c0a4ab0",
}

THREAD_ENVIRONMENT = {
    "GEOTARGET_TYPED_SEMANTIC_RUNTIME_ROOT": str(RUNTIME_ROOT),
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "JULIA_NUM_GC_THREADS": "1",
    "MALLOC_ARENA_MAX": "2",
}

FORBIDDEN_KEYS = frozenset(
    {
        "truth",
        "known_truth",
        "known_target",
        "expected_target",
        "expected_target_count",
        "target_values",
        "gold",
        "score",
        "scorer_output",
        "historical_result",
        "authority",
    }
)

_LINE_REFLECT = """function qreflect(value::QPoint, mirror::QLine)
  foot = qfoot(value, mirror)
  return qsub(qscale(foot, 2), value)
end
"""
_POINT_REFLECT = """
function qreflect(value::QPoint, center::QPoint)
  return qsub(qscale(center, 2), value)
end
"""
_INSTRUMENTED_POINT_REFLECT = """
const GEOTARGET_QREFLECT_POINT_POINT_ACTIVATED = Ref(false)

function qreflect(value::QPoint, center::QPoint)
  GEOTARGET_QREFLECT_POINT_POINT_ACTIVATED[] = true
  return qsub(qscale(center, 2), value)
end
"""
_LEDGER_SEAM = '    "operation_counts" => operation_counts,\n'
_LEDGER_WITH_ACTIVATION = (
    '    "operation_counts" => operation_counts,\n'
    '    "qreflect_point_point_dispatch_activated" => '
    'GEOTARGET_QREFLECT_POINT_POINT_ACTIVATED[],\n'
)


class PortfolioFailure(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_frozen_dependencies() -> dict[str, str]:
    observed = {
        str(path): _sha256(path.read_bytes()) if path.is_file() else "MISSING"
        for path in FROZEN_DEPENDENCIES
    }
    expected = {str(path): digest for path, digest in FROZEN_DEPENDENCIES.items()}
    if observed != expected:
        raise PortfolioFailure("frozen union exact-coordinate closure changed")
    # The qreflect reference must be exactly the sector QQBar program plus the
    # one already-generated QPoint/QPoint overload.  This makes the union
    # transform auditable and proves the QLine implementation is untouched.
    sector = SECTOR_QQBAR.read_text(encoding="utf-8")
    reference = QREFLECT_REFERENCE_QQBAR.read_text(encoding="utf-8")
    if sector.count(_LINE_REFLECT) != 1:
        raise PortfolioFailure("qreflect QLine seam changed")
    if sector.replace(_LINE_REFLECT, _LINE_REFLECT + _POINT_REFLECT) != reference:
        raise PortfolioFailure("qreflect reference is not the one-opcode superset")
    return observed


def _forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key).strip().lower().replace("-", "_")
            if key in FORBIDDEN_KEYS or key.endswith("_authority") or _forbidden(item):
                return True
    elif isinstance(value, list):
        return any(_forbidden(item) for item in value)
    return False


def _source_document(path: Path, expected_sha256: str) -> tuple[bytes, dict[str, Any]]:
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_SOURCE_BYTES or _sha256(payload) != expected_sha256:
        raise PortfolioFailure("source bytes or digest invalid")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PortfolioFailure("source is not JSON") from error
    variables = document.get("variables") if isinstance(document, Mapping) else None
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if (
        not isinstance(document, dict)
        or document.get("task") != "solve"
        or not isinstance(names, list)
        or not names
        or not all(isinstance(name, str) and name for name in names)
        or document.get("post_process") not in (None, "")
        or _forbidden(document)
    ):
        raise PortfolioFailure("source is outside truth-blind solve authority")
    return payload, document


def _endpoint_sha256(endpoint: Sequence[float]) -> str:
    values = tuple(float(value) for value in endpoint)
    payload = struct.pack(">I", len(values)) + b"".join(
        struct.pack(">d", value) for value in values
    )
    return _sha256(payload)


def _descriptor_identity(value: object) -> tuple[tuple[int, ...], int] | None:
    if not isinstance(value, Mapping):
        return None
    polynomial = value.get("minimal_polynomial_high_to_low")
    index = value.get("selected_real_root_index")
    if (
        not isinstance(polynomial, list)
        or len(polynomial) < 2
        or not all(isinstance(item, int) and not isinstance(item, bool) for item in polynomial)
        or not isinstance(index, int)
        or isinstance(index, bool)
        or index < 0
    ):
        return None
    content = 0
    for coefficient in polynomial:
        content = gcd(content, abs(coefficient))
    if content == 0:
        return None
    canonical = [coefficient // content for coefficient in polynomial]
    if canonical[0] < 0:
        canonical = [-coefficient for coefficient in canonical]
    return tuple(canonical), index


def _load_frozen_module(name: str, path: Path):
    loaded = sys.modules.get(name)
    if loaded is not None:
        return loaded
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise PortfolioFailure("frozen module unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _authority_ready(
    record: object,
    *,
    source_document: Mapping[str, Any],
    source_sha256: str,
    endpoint_sha256: str,
) -> bool:
    boundary = _load_frozen_module(
        "geotarget_categorical_union_authority_boundary", AUTHORITY_BOUNDARY
    )
    descriptor = (
        boundary.exact_descriptor(record.get("descriptor"))
        if isinstance(record, Mapping)
        else None
    )
    return bool(
        isinstance(record, Mapping)
        and record.get("schema_version") == SCHEMA
        and record.get("completed") is True
        and record.get("status") == "EXACT_COORDINATE_TARGET_AUTHORITY_READY"
        and record.get("authority_pass") is True
        and record.get("source_sha256") == source_sha256
        and record.get("endpoint_float64_sha256") == endpoint_sha256
        and record.get("truth_used") is False
        and record.get("case_family_known_target_count_routing") is False
        and record.get("source_or_problem_modified") is False
        and record.get("bounds_added_or_inferred") is False
        and record.get("coordinate_reparameterization") is False
        and record.get("target_set_completeness_claim") is False
        and record.get("within_fallback_wall_budget") is True
        and descriptor is not None
        and boundary.nested_exact_authority_matches_source(
            record, descriptor, source_document, source_sha256
        )
    )


def _union_qqbar_source() -> str:
    """Return the sector worker plus the exact generated qreflect overload."""

    sector = SECTOR_QQBAR.read_text(encoding="utf-8")
    reference = QREFLECT_REFERENCE_QQBAR.read_text(encoding="utf-8")
    if sector.count(_LINE_REFLECT) != 1:
        raise PortfolioFailure("qreflect QLine seam changed")
    uninstrumented = sector.replace(
        _LINE_REFLECT, _LINE_REFLECT + _POINT_REFLECT
    )
    if uninstrumented != reference:
        raise PortfolioFailure("qreflect one-opcode reference mismatch")
    union = sector.replace(
        _LINE_REFLECT, _LINE_REFLECT + _INSTRUMENTED_POINT_REFLECT
    )
    if union.count(_LEDGER_SEAM) != 1:
        raise PortfolioFailure("QQBar activation ledger seam changed")
    return union.replace(_LEDGER_SEAM, _LEDGER_WITH_ACTIVATION)


def _load_sector_worker():
    name = "geotarget_categorical_union_sector_worker"
    loaded = sys.modules.get(name)
    if loaded is not None:
        return loaded
    # The frozen sector files use local absolute imports.  Keep the insertion
    # limited to this disposable exact-worker process.
    sys.path.insert(0, str(SECTOR_ROOT))
    try:
        return _load_frozen_module(name, SECTOR_WORKER)
    finally:
        try:
            sys.path.remove(str(SECTOR_ROOT))
        except ValueError:
            pass


def _install_activation_capture(module: Any) -> dict[str, bool]:
    exact = module.exact_candidate
    state = getattr(exact, "_categorical_union_activation_state", None)
    if isinstance(state, dict):
        state["qreflect"] = False
        state["sector_angle"] = False
        return state
    prior = exact._run_qqbar
    state = {"qreflect": False, "sector_angle": False}

    def captured(job: Mapping[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
        replay = prior(job, timeout_seconds=timeout_seconds)
        state["qreflect"] = bool(
            isinstance(replay, Mapping)
            and replay.get("qreflect_point_point_dispatch_activated") is True
        )
        state["sector_angle"] = bool(
            isinstance(replay, Mapping)
            and replay.get("typed_semantic_equal_repair") is True
            and replay.get("sector_certified_integer_angle_relation") is True
        )
        return replay

    exact._run_qqbar = captured
    exact._categorical_union_activation_state = state
    return state


@contextmanager
def _installed_union_worker() -> Iterator[tuple[Any, dict[str, bool]]]:
    module = _load_sector_worker()
    state = _install_activation_capture(module)
    previous = module.exact_candidate.QQBAR_WORKER
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".jl", delete=False
        ) as stream:
            stream.write(_union_qqbar_source())
            temporary = Path(stream.name)
        module.exact_candidate.QQBAR_WORKER = temporary
        yield module, state
    finally:
        module.exact_candidate.QQBAR_WORKER = previous
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _decorate_activation(
    record: dict[str, Any], *, qreflect: bool, sector_angle: bool
) -> dict[str, Any]:
    routes = [
        route
        for route, active in (
            ("qreflect", qreflect),
            ("sector_angle", sector_angle),
        )
        if active
    ]
    if not routes:
        return record
    result = dict(record)
    result["categorical_exact_coordinate_portfolio"] = {
        "schema_version": PORTFOLIO_SCHEMA,
        "activated_routes": routes,
        "categorical_route_activated": True,
        "actual_exact_dispatch_activation": True,
        "single_numeric_refinement": True,
        "qreflect_point_point_exact_opcode_only": True,
        "sector_internal_generic_baseline_first": True,
        "sector_internal_baseline_budget_fraction": 0.75,
        "sector_internal_side_budget_fraction_maximum": 0.25,
        "ordinary_endpoint_consumed": True,
        "canonical_exact_outer_revalidation_required": True,
        "target_set_completeness_claim": False,
        "truth_used": False,
    }
    result["target_set_completeness_claim"] = False
    return result


def run_portfolio(
    *,
    source: Path,
    source_sha256: str,
    endpoint: Sequence[float],
    endpoint_sha256: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    verify_frozen_dependencies()
    requested_runtime = os.environ.get("GEOTARGET_TYPED_SEMANTIC_RUNTIME_ROOT")
    if (
        requested_runtime is not None
        and Path(requested_runtime).resolve() != RUNTIME_ROOT
    ):
        raise PortfolioFailure("alternate typed-semantic runtime root is forbidden")
    if (
        not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0.5
        or not endpoint
        or not all(math.isfinite(float(value)) for value in endpoint)
        or _endpoint_sha256(endpoint) != endpoint_sha256
    ):
        raise PortfolioFailure("endpoint or wall budget invalid")
    source_payload, document = _source_document(source, source_sha256)
    if len(document["variables"]["names"]) != len(endpoint):
        raise PortfolioFailure("endpoint dimension differs from source")
    previous_environment = {
        key: os.environ.get(key) for key in THREAD_ENVIRONMENT
    }
    os.environ.update(THREAD_ENVIRONMENT)
    try:
        with _installed_union_worker() as (worker, activation):
            result = worker.run_fallback(
                source=source,
                source_sha256=source_sha256,
                endpoint=tuple(float(value) for value in endpoint),
                endpoint_sha256=endpoint_sha256,
                timeout_seconds=timeout_seconds,
            )
    finally:
        for key, value in previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if source.read_bytes() != source_payload or not isinstance(result, dict):
        raise PortfolioFailure("union worker terminal or source binding changed")
    ready = _authority_ready(
        result,
        source_document=document,
        source_sha256=source_sha256,
        endpoint_sha256=endpoint_sha256,
    )
    qreflect = bool(ready and activation.get("qreflect") is True)
    sector_angle = bool(ready and activation.get("sector_angle") is True)
    return _decorate_activation(
        result, qreflect=qreflect, sector_angle=sector_angle
    )


def _rejected(
    *, source_sha256: str, endpoint_sha256: str, failure: str
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "completed": True,
        "source_sha256": source_sha256,
        "endpoint_float64_sha256": endpoint_sha256,
        "status": "EXACT_COORDINATE_FALLBACK_REJECTED",
        "authority_pass": False,
        "descriptor": None,
        "failure": failure,
        "truth_used": False,
        "case_family_known_target_count_routing": False,
        "source_or_problem_modified": False,
        "bounds_added_or_inferred": False,
        "coordinate_reparameterization": False,
        "target_set_completeness_claim": False,
        "within_fallback_wall_budget": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--endpoint-sha256", required=True)
    parser.add_argument("--timeout-seconds", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        endpoint = json.loads(arguments.endpoint)
        if not isinstance(endpoint, list):
            raise PortfolioFailure("endpoint is not an array")
        result = run_portfolio(
            source=arguments.source,
            source_sha256=arguments.source_sha256,
            endpoint=endpoint,
            endpoint_sha256=arguments.endpoint_sha256,
            timeout_seconds=arguments.timeout_seconds,
        )
    except Exception as error:
        result = _rejected(
            source_sha256=arguments.source_sha256,
            endpoint_sha256=arguments.endpoint_sha256,
            failure=type(error).__name__,
        )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=arguments.output.parent, delete=False
    ) as stream:
        json.dump(result, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, arguments.output)
    print(
        json.dumps(
            {"status": result["status"], "authority_pass": result["authority_pass"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
