#!/usr/bin/env python3.12
"""Frozen, truth-blind admission and dependency bindings for selected execution."""

from __future__ import annotations

from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
STATIC_RUNNER = HERE / "run_static_applicability.py"
MSOLVE_DIR = (
    RUNTIME_ROOT / "research/experiments/EXP-REAL61-004/msolve_exact_witness"
)
QQBAR_DIR = RUNTIME_ROOT / "research/experiments/EXP-REAL61-004/qqbar_exact_replay"
TARGET_ELIMINATION_DIR = (
    RUNTIME_ROOT / "research/experiments/EXP-REAL61-002/target_elimination"
)
MSOLVE_BINARY = MSOLVE_DIR / "vendor/prebuilt/msolve"
FACTOR_PYTHON = Path("/home/kabatan/work/geosolver/.venv/bin/python")

DEPENDENCY_SHA256 = {
    STATIC_RUNNER: "8a0152d6ccb47885a923c50d5fea1e464657e2bf9ce953e2282c39f49d3f97bd",
    MSOLVE_DIR / "run_msolve.py": "1d874dcd59e93dbed0f057ac578a694309bc8ec2ba7c5c83c68a9ef722bddf23",
    MSOLVE_DIR / "inspect_result.py": "fb730ca08d4c7ba0187c5d4dad80a3a57bb9844c9bb3f094c065c234b37d41ec",
    MSOLVE_DIR / "factor_selected.py": "ef5085fce9ded55e790032e04a5d487498f9a2ebc6d57753e7d2547cc15b078d",
    MSOLVE_DIR / "msolve_output.py": "efd2d8b71bcaebcaaddc926f06e849993b931036e375d91d5a30679fa8e294c6",
    MSOLVE_DIR / "replay_rur_qqbar.py": "a373273b08bafcae746f57a9362be8f6b499c04bc9de07a6061829a324c400ad",
    MSOLVE_DIR / "replay_rur_witness.py": "bb988e189bbce91a0acbd3a96799a27875c8e5d049cb1b7ad2638bcf010c6af7",
    MSOLVE_DIR / "rur_qqbar_worker.jl": "4cae5df88f3f6b3b5506d78559d6c6d87e567eb47ed0e85686b313c515d79ace",
    MSOLVE_BINARY: "d42facbdb8e49e946cc100a2104621df4ddfdc5c8960bba706f40c12ceb4b31c",
    QQBAR_DIR / "worker.py": "926bb2da8308b3a8b7275c3f2628b288a45f67138e27f25f6a23c53434cd4371",
    QQBAR_DIR / "qqbar_worker.jl": "3ac6415600da77f8748a11d15fa47eb3dcb9f8deada375388fc762a155df0b4a",
    QQBAR_DIR / "dag_compile.py": "9b83181004a8ea2ea73f2974129e37ce252f7d352937b9f8b601b39eddf03d18",
    RUNTIME_ROOT / "research/infrastructure/exact_evidence_v2/exact_evidence.py": "fa5ad18f725da11bee28a66afb3b54a3188f0fccf0544de3b83250d47c31bcc4",
    TARGET_ELIMINATION_DIR / "Project.toml": "9f39a2eb827fcc842513037ed5d9debbe1e1cf15a24e29111645917e9acaa6c7",
    TARGET_ELIMINATION_DIR / "Manifest.toml": "0b93cd67d522d4cce3bea7b3a754109a972e1eb2ef7fabe7eecb6c7a3cb19b42",
    RUNTIME_ROOT / "research/infrastructure/memory_safety/safe_subprocess.py": "76aa547f235bd0ae11c8b567461384b22537a9b98c990db2ed126db0a19b55c5",
    RUNTIME_ROOT / "research/harness/exclusive_run.py": "c341bfc6b86a8b3f7c0c0059272034459068ad168262a898ed87faf6e17e81c5",
    HERE / "lossless_transport.py": "43fde3a479c2335f1e0311d990810bf4983d4c50f268a7968512cccb1daec521",
}

ADMISSION_STAGES = (
    "request_contract_ready",
    "reversible_qq_exact_cover",
    "equations_ge_variables",
    "endpoint_target_proposal_compatible",
    "dimension0_selected_factor_possible",
    "fixed_degree_cost_caps",
    "eligible",
)


class SelectedExecutionError(ValueError):
    """A frozen selected-execution invariant failed closed."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256_bytes(canonical_bytes(value))


def load_module(name: str, path: Path):
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise SelectedExecutionError("frozen module is unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def verify_frozen_dependencies() -> None:
    for path, expected in DEPENDENCY_SHA256.items():
        try:
            actual = sha256_bytes(path.read_bytes())
        except OSError as error:
            raise SelectedExecutionError("frozen dependency is unavailable") from error
        if actual != expected:
            raise SelectedExecutionError("frozen dependency digest changed")
    if not MSOLVE_BINARY.is_file() or not MSOLVE_BINARY.stat().st_mode & 0o111:
        raise SelectedExecutionError("frozen msolve executable is unavailable")
    if not FACTOR_PYTHON.is_file():
        raise SelectedExecutionError("frozen python-flint interpreter is unavailable")


def load_admission_dependencies() -> tuple[Any, Any, Any, Any]:
    verify_frozen_dependencies()
    static = load_module("msolve_selected_frozen_static_admission", STATIC_RUNNER)
    source_compiler, load_problem_bundle, build_ir_evaluator = (
        static._load_dependencies()
    )
    return static, source_compiler, load_problem_bundle, build_ir_evaluator


def classify_request(
    request: object,
    *,
    dependencies: tuple[Any, Any, Any, Any],
) -> dict[str, Any]:
    """Re-run the exact static census predicates and retain no case identity."""

    static, source_compiler, load_problem_bundle, build_ir_evaluator = dependencies
    passed: list[str] = []
    try:
        if (
            not isinstance(request, Mapping)
            or set(request) != static.REQUEST_KEYS
            or static.FORBIDDEN_REQUEST_KEYS & set(request)
        ):
            raise SelectedExecutionError("request contract rejected")
        source_path = static._bounded_source_path(request["source_path"])
        source_bytes = source_path.read_bytes()
        document = json.loads(source_bytes)
        if not isinstance(document, dict) or "id" in document:
            raise SelectedExecutionError("anonymous source projection rejected")
        endpoint = static._endpoint(request["endpoint"])
        root, relation = static._degree_one_root(
            request["candidate_relation_high_to_low"]
        )
        passed.append("request_contract_ready")

        compiled, msolve_input = source_compiler.compile_source_document(
            document, source_bytes=source_bytes
        )
        if not (
            compiled.get("status") == "ELIGIBLE_MSOLVE_DIMENSION_PROBE"
            and compiled.get("truth_used") is False
            and compiled.get("known_target_count_used") is False
            and compiled.get("case_identity_routing") is False
            and compiled.get("canonical_validation_required") is True
            and compiled.get("dimension_status") == "MUST_BE_CLASSIFIED_BY_MSOLVE"
            and compiled.get("source_variable_names")
            == document.get("variables", {}).get("names")
            and set(compiled.get("source_variable_names", [])).issubset(
                compiled.get("cover_variable_names", [])
            )
            and len(endpoint) == len(compiled.get("source_variable_names", []))
        ):
            raise SelectedExecutionError("reversible QQ cover rejected")
        symbols, polynomials = static._compile_polynomials(compiled)
        passed.append("reversible_qq_exact_cover")

        if len(polynomials) < len(symbols):
            raise SelectedExecutionError("height lower bound excludes dimension zero")
        passed.append("equations_ge_variables")

        if not static._answer_is_proposal_compatible(
            document,
            endpoint,
            root,
            load_problem_bundle=load_problem_bundle,
            build_ir_evaluator=build_ir_evaluator,
        ):
            raise SelectedExecutionError("endpoint target box misses proposal")
        passed.append("endpoint_target_proposal_compatible")

        matching_product = static._minimum_matching_degree_product(
            symbols, polynomials
        )
        if matching_product is None:
            raise SelectedExecutionError("no structural square subsystem")
        passed.append("dimension0_selected_factor_possible")

        if not static._cost_caps_pass(
            compiled, polynomials, relation, matching_product
        ):
            raise SelectedExecutionError("fixed cost cap exceeded")
        passed.extend(("fixed_degree_cost_caps", "eligible"))
        static_signature = static._canonical_sha256(
            {
                "cover_shape": compiled.get("cover_shape"),
                "variable_count": len(symbols),
                "equation_count": len(polynomials),
                "predicate_count": len(compiled.get("predicates", [])),
                "maximum_degree": max(
                    int(polynomial.total_degree()) for polynomial in polynomials
                ),
                "total_monomial_bucket": sum(
                    len(polynomial.terms()) for polynomial in polynomials
                )
                // 16,
                "minimum_matching_degree_product": matching_product,
                "endpoint_dimension": len(endpoint),
            }
        )
        return {
            "eligible": True,
            "passed_stages": passed,
            "source_path": source_path,
            "source_bytes": source_bytes,
            "source_sha256": sha256_bytes(source_bytes),
            "source": document,
            "endpoint": endpoint,
            "target_root": root,
            "target_relation": relation,
            "compiled": compiled,
            "msolve_input": msolve_input,
            "static_signature": static_signature,
        }
    except Exception as error:
        return {
            "eligible": False,
            "passed_stages": passed,
            "error_type": type(error).__name__,
            "error": str(error)[:512],
        }


def target_descriptor(root: Fraction, relation: tuple[int, int]) -> dict[str, Any]:
    leading, constant = relation
    rational = str(root.numerator) if root.denominator == 1 else str(root)
    return {
        "coefficients_high_to_low": [leading, constant],
        "primitive": True,
        "square_free": True,
        "irreducible_over_Q": True,
        "isolating_interval": {
            "left": rational,
            "right": rational,
            "multiplicity": 1,
        },
    }

