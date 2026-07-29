"""Differential qualification gate for a candidate compiled geometry kernel.

This module is deliberately outside the solve path.  A candidate kernel must
provide the small adapter protocol below; the frozen/reference evaluator
remains the oracle for every generated probe.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import math
import struct
import textwrap
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np

QUALIFICATION_CORES = (1, 2, 4, 8, 15)
REPORT_SCHEMA = "geotarget.compiled-kernel-qualification/v1"


@dataclass(frozen=True)
class Observation:
    """All decision-bearing output from one evaluator callback."""

    values: tuple[float, ...]
    transcendental_indices: tuple[int, ...] = ()
    transcendental_branches: tuple[str, ...] = ()
    residuals: tuple[float, ...] = ()
    transcendental_residual_indices: tuple[int, ...] = ()
    transcendental_residual_branches: tuple[str, ...] = ()
    guard_outcomes: tuple[bool, ...] = ()
    guard_violations: tuple[str, ...] = ()
    hard_feasible: bool = False
    hard_failure_tags: tuple[str, ...] = ()
    hard_min_margin: float | None = None
    threshold_decisions: tuple[str, ...] = ()
    selector_trace: tuple[str, ...] = ()
    candidate_record: Mapping[str, Any] | None = None
    exception_type: str | None = None
    exception_stage: str | None = None
    nonfinite_classification: tuple[str, ...] = ()
    status: str = "ok"

    @classmethod
    def from_value(cls, value: Observation | Mapping[str, Any]) -> Observation:
        if isinstance(value, cls):
            return value
        return cls(
            values=tuple(float(item) for item in value.get("values", ())),
            transcendental_indices=tuple(
                int(item) for item in value.get("transcendental_indices", ())
            ),
            transcendental_branches=tuple(
                str(item) for item in value.get("transcendental_branches", ())
            ),
            residuals=tuple(float(item) for item in value.get("residuals", ())),
            transcendental_residual_indices=tuple(
                int(item)
                for item in value.get("transcendental_residual_indices", ())
            ),
            transcendental_residual_branches=tuple(
                str(item)
                for item in value.get("transcendental_residual_branches", ())
            ),
            guard_outcomes=tuple(bool(item) for item in value.get("guard_outcomes", ())),
            guard_violations=tuple(
                str(item) for item in value.get("guard_violations", ())
            ),
            hard_feasible=bool(value.get("hard_feasible", False)),
            hard_failure_tags=tuple(
                str(item) for item in value.get("hard_failure_tags", ())
            ),
            hard_min_margin=(
                None
                if value.get("hard_min_margin") is None
                else float(value["hard_min_margin"])
            ),
            threshold_decisions=tuple(
                str(item) for item in value.get("threshold_decisions", ())
            ),
            selector_trace=tuple(str(item) for item in value.get("selector_trace", ())),
            candidate_record=value.get("candidate_record"),
            exception_type=(
                None
                if value.get("exception_type") is None
                else str(value["exception_type"])
            ),
            exception_stage=(
                None
                if value.get("exception_stage") is None
                else str(value["exception_stage"])
            ),
            nonfinite_classification=tuple(
                str(item) for item in value.get("nonfinite_classification", ())
            ),
            status=str(value.get("status", "ok")),
        )


class PreparedKernelCase(Protocol):
    dimension: int
    lower: Sequence[float]
    upper: Sequence[float]
    compiled_supported: bool
    fallback_reason: str | None
    support_decision_trace: Mapping[str, Any]

    def reference(self, point: np.ndarray) -> Observation | Mapping[str, Any]: ...

    def candidate(self, point: np.ndarray) -> Observation | Mapping[str, Any]: ...

    def optimizer_replay_probes(self) -> Sequence[Mapping[str, Any]]: ...


class KernelQualificationAdapter(Protocol):
    def compiler_manifest(self) -> Mapping[str, Any]: ...

    def support_decision_source(self) -> str: ...

    def qualification_capabilities(self) -> Mapping[str, Any]: ...

    def prepare(
        self, problem: Mapping[str, Any], *, cores: int
    ) -> PreparedKernelCase: ...


@dataclass(frozen=True)
class HarnessConfig:
    random_probes_per_problem: int = 64
    maximum_boundary_coordinates: int = 8
    require_fallback_path: bool = True
    require_optimizer_replay: bool = True
    report_mode: Literal[
        "production_strict", "experimental_numeric_equivalence"
    ] = "production_strict"
    cores: tuple[int, ...] = QUALIFICATION_CORES
    maximum_mismatch_examples: int = 50


@dataclass(frozen=True)
class Probe:
    kind: str
    ordinal: int
    point: np.ndarray = field(repr=False)
    expected_candidate_record: Mapping[str, Any] | None = field(
        default=None, repr=False
    )


def _float_bytes(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _ordered_float_integer(value: float) -> int:
    bits = struct.unpack(">Q", _float_bytes(value))[0]
    return (~bits & ((1 << 64) - 1)) if bits >> 63 else bits | (1 << 63)


def ulp_distance(left: float, right: float) -> int:
    if math.isnan(left) or math.isnan(right):
        return 0 if _float_bytes(left) == _float_bytes(right) else 2**64
    return abs(_ordered_float_integer(left) - _ordered_float_integer(right))


def _within_2_ulp(left: float, right: float) -> bool:
    if _float_bytes(left) == _float_bytes(right):
        return True
    if not math.isfinite(left) or not math.isfinite(right):
        return False
    if left == 0.0 or right == 0.0:
        return False
    return ulp_distance(left, right) <= 2


def _canonical_record(value: Any) -> bytes:
    """Type- and binary64-preserving encoding for candidate-record equality."""

    if isinstance(value, np.bool_):
        value = bool(value)
    elif isinstance(value, np.integer):
        value = int(value)
    elif isinstance(value, np.floating):
        value = float(value)
    if value is None:
        return b"n"
    if isinstance(value, bool):
        return b"b1" if value else b"b0"
    if isinstance(value, int):
        return b"i" + str(value).encode("ascii") + b";"
    if isinstance(value, float):
        return b"f" + _float_bytes(value)
    if isinstance(value, str):
        payload = value.encode("utf-8")
        return b"s" + str(len(payload)).encode("ascii") + b":" + payload
    if isinstance(value, Mapping):
        encoded = []
        for key, item in value.items():
            encoded.append((_canonical_record(key), _canonical_record(item)))
        encoded.sort(key=lambda pair: pair[0])
        return b"m" + b"".join(
            str(len(key)).encode("ascii")
            + b":"
            + key
            + str(len(item)).encode("ascii")
            + b":"
            + item
            for key, item in encoded
        )
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        items = [_canonical_record(item) for item in value]
        return b"l" + b"".join(
            str(len(item)).encode("ascii") + b":" + item for item in items
        )
    raise TypeError(f"candidate record contains unsupported {type(value).__name__}")


def _update_observation_digest(
    digest: Any, probe: Probe, observation: Observation
) -> None:
    digest.update(probe.kind.encode("utf-8") + b"\0")
    digest.update(probe.point.astype(">f8", copy=False).tobytes() + b"\0")
    digest.update(_canonical_record(observation.__dict__) + b"\0")


def compare_observations(
    reference: Observation | Mapping[str, Any],
    candidate: Observation | Mapping[str, Any],
    *,
    allow_transcendental_2ulp: bool = False,
) -> tuple[str, ...]:
    """Apply the immutable bitwise/2-ULP differential contract."""

    oracle = Observation.from_value(reference)
    observed = Observation.from_value(candidate)
    mismatches: list[str] = []
    if oracle.status != observed.status:
        mismatches.append("status")
    if len(oracle.values) != len(observed.values):
        mismatches.append("value_count")
    if oracle.transcendental_indices != observed.transcendental_indices:
        mismatches.append("transcendental_indices")
    if oracle.transcendental_branches != observed.transcendental_branches:
        mismatches.append("transcendental_branch")
    if (
        len(oracle.transcendental_indices) != len(oracle.transcendental_branches)
        or len(observed.transcendental_indices)
        != len(observed.transcendental_branches)
        or any(
            index < 0 or index >= len(oracle.values)
            for index in oracle.transcendental_indices
        )
    ):
        mismatches.append("transcendental_branch_coverage")
    transcendental = set(oracle.transcendental_indices)
    for index, (expected, actual) in enumerate(
        zip(oracle.values, observed.values, strict=False)
    ):
        if allow_transcendental_2ulp and index in transcendental:
            if not _within_2_ulp(expected, actual):
                mismatches.append(f"value[{index}]:more_than_2_ulp")
        elif _float_bytes(expected) != _float_bytes(actual):
            mismatches.append(f"value[{index}]:not_bitwise_equal")
    if (
        oracle.transcendental_residual_indices
        != observed.transcendental_residual_indices
    ):
        mismatches.append("transcendental_residual_indices")
    if (
        oracle.transcendental_residual_branches
        != observed.transcendental_residual_branches
    ):
        mismatches.append("transcendental_residual_branch")
    if (
        len(oracle.transcendental_residual_indices)
        != len(oracle.transcendental_residual_branches)
        or len(observed.transcendental_residual_indices)
        != len(observed.transcendental_residual_branches)
        or any(
            index < 0 or index >= len(oracle.residuals)
            for index in oracle.transcendental_residual_indices
        )
    ):
        mismatches.append("transcendental_residual_branch_coverage")
    residual_transcendental = set(oracle.transcendental_residual_indices)
    residual_mismatch = len(oracle.residuals) != len(observed.residuals)
    for index, (expected, actual) in enumerate(
        zip(oracle.residuals, observed.residuals, strict=False)
    ):
        if allow_transcendental_2ulp and index in residual_transcendental:
            residual_mismatch = residual_mismatch or not _within_2_ulp(expected, actual)
        else:
            residual_mismatch = residual_mismatch or (
                _float_bytes(expected) != _float_bytes(actual)
            )
    if residual_mismatch:
        mismatches.append("residuals")
    if oracle.guard_outcomes != observed.guard_outcomes:
        mismatches.append("guards")
    if oracle.guard_violations != observed.guard_violations:
        mismatches.append("guard_violations")
    if oracle.hard_feasible != observed.hard_feasible:
        mismatches.append("hard_feasibility")
    if oracle.hard_failure_tags != observed.hard_failure_tags:
        mismatches.append("hard_failure_tags")
    if (
        oracle.hard_min_margin is None
        or observed.hard_min_margin is None
    ):
        if oracle.hard_min_margin is not observed.hard_min_margin:
            mismatches.append("hard_min_margin")
    elif _float_bytes(oracle.hard_min_margin) != _float_bytes(
        observed.hard_min_margin
    ):
        mismatches.append("hard_min_margin")
    if oracle.threshold_decisions != observed.threshold_decisions:
        mismatches.append("threshold_decisions")
    if oracle.selector_trace != observed.selector_trace:
        mismatches.append("selector_trace")
    try:
        record_equal = _canonical_record(oracle.candidate_record) == _canonical_record(
            observed.candidate_record
        )
    except TypeError:
        record_equal = False
    if not record_equal:
        mismatches.append("candidate_record")
    if oracle.exception_type != observed.exception_type:
        mismatches.append("exception_type")
    if oracle.exception_stage != observed.exception_stage:
        mismatches.append("exception_stage")
    if oracle.nonfinite_classification != observed.nonfinite_classification:
        mismatches.append("nonfinite_classification")
    return tuple(mismatches)


def compare_core_observations(
    one_core: Observation | Mapping[str, Any],
    other_core: Observation | Mapping[str, Any],
) -> tuple[str, ...]:
    """Require bitwise identity across core counts, including transcendentals."""

    baseline = Observation.from_value(one_core)
    observed = Observation.from_value(other_core)
    mismatches = list(compare_observations(baseline, observed))
    if len(baseline.values) == len(observed.values) and any(
        _float_bytes(expected) != _float_bytes(actual)
        for expected, actual in zip(baseline.values, observed.values, strict=True)
    ):
        mismatches.append("core_value_not_bitwise_equal")
    return tuple(dict.fromkeys(mismatches))


def _finite_bound(value: float, fallback: float) -> float:
    return float(value) if math.isfinite(float(value)) else fallback


def generate_probes(
    problem_sha256: str,
    lower: Sequence[float],
    upper: Sequence[float],
    config: HarnessConfig,
) -> tuple[Probe, ...]:
    """Generate deterministic random, boundary, and degenerate probes."""

    low = np.asarray(lower, dtype=np.float64)
    high = np.asarray(upper, dtype=np.float64)
    if low.shape != high.shape or low.ndim != 1:
        raise ValueError("kernel bounds must be equally sized vectors")
    bounded_low = np.asarray(
        [_finite_bound(value, -2.0) for value in low], dtype=np.float64
    )
    bounded_high = np.asarray(
        [_finite_bound(value, 2.0) for value in high], dtype=np.float64
    )
    if np.any(bounded_low > bounded_high):
        raise ValueError("kernel lower bound exceeds upper bound")
    midpoint = bounded_low + (bounded_high - bounded_low) / 2.0
    seed = int(problem_sha256[:16], 16)
    random = np.random.Generator(np.random.PCG64(seed))
    probes: list[Probe] = []
    for ordinal in range(config.random_probes_per_problem):
        probes.append(
            Probe(
                "random",
                ordinal,
                random.uniform(bounded_low, bounded_high).astype(np.float64),
            )
        )
    for coordinate in range(min(len(low), config.maximum_boundary_coordinates)):
        for label, value in (
            ("lower", bounded_low[coordinate]),
            ("lower_inside", np.nextafter(bounded_low[coordinate], math.inf)),
            ("upper_inside", np.nextafter(bounded_high[coordinate], -math.inf)),
            ("upper", bounded_high[coordinate]),
        ):
            point = midpoint.copy()
            point[coordinate] = value
            probes.append(Probe(f"boundary:{label}", coordinate, point))
    degenerate = (
        np.zeros_like(midpoint),
        np.full_like(midpoint, midpoint[0] if len(midpoint) else 0.0),
        np.full_like(midpoint, np.finfo(np.float64).tiny),
        np.full_like(midpoint, -np.finfo(np.float64).tiny),
        midpoint.copy(),
    )
    probes.extend(
        Probe("degenerate", ordinal, point)
        for ordinal, point in enumerate(degenerate)
    )
    return tuple(probes)


def _replay_probes(
    rows: Sequence[Mapping[str, Any]], *, ordinal_start: int = 0
) -> tuple[Probe, ...]:
    probes = []
    for offset, row in enumerate(rows):
        point = np.asarray(row.get("point"), dtype=np.float64)
        if point.ndim != 1:
            raise ValueError("optimizer replay point must be a vector")
        trace_id = str(row.get("trace_id", ordinal_start + offset))
        candidate_record = row.get("candidate_record")
        if candidate_record is not None:
            if not isinstance(candidate_record, Mapping):
                raise ValueError("optimizer candidate record must be an object")
            required = {"endpoint_sha256", "record_id", "admission_role"}
            if not required.issubset(candidate_record):
                raise ValueError(
                    "optimizer candidate record is missing endpoint/admission identity"
                )
        probes.append(
            Probe(
                f"optimizer_replay:{trace_id}",
                ordinal_start + offset,
                point,
                candidate_record,
            )
        )
    return tuple(probes)


def load_replay_trace(path: Path) -> dict[str, tuple[Probe, ...]]:
    """Load `{case_id, trace_id, point}` rows from JSON or JSON Lines."""

    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        rows = payload.get("probes") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("optimizer replay trace must contain probe rows")
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("optimizer replay row is missing case_id")
        grouped.setdefault(case_id, []).append(row)
    return {case_id: _replay_probes(values) for case_id, values in grouped.items()}


def load_corpus(corpus: Path) -> tuple[tuple[str, dict[str, Any], str], ...]:
    paths = sorted(corpus.glob("*/problem.json"))
    if len(paths) != 145:
        raise ValueError(f"compiled-kernel qualification requires 145 problems, got {len(paths)}")
    cases = []
    for path in paths:
        payload = path.read_bytes()
        problem = json.loads(payload)
        cases.append((path.parent.name, problem, hashlib.sha256(payload).hexdigest()))
    return tuple(cases)


def independent_ast_composition_fixtures() -> tuple[dict[str, Any], ...]:
    """Corpus-independent V15 compositions for selector/geometry generality."""

    fixtures = []
    for selector in ("near=Q", "far=Q", "exclude=A"):
        name = selector.split("=", 1)[0]
        fixtures.append(
            {
                "task": "solve",
                "id": f"kernel-independent-{name}",
                "variables": {"names": ["cx", "cy", "t"]},
                "construction": [
                    {"name": "A", "expr": "Point(0, 0)"},
                    {"name": "B", "expr": "Point(4, 0)"},
                    {"name": "C", "expr": "Point(cx, cy)"},
                    {"name": "gamma", "expr": "Circle(A, Distance(A, B))"},
                    {"name": "Q", "expr": "PointOnCircle(gamma, t)"},
                    {"name": "ell", "expr": "Line(A, C)"},
                    {
                        "name": "P",
                        "expr": f"Intersect(ell, gamma, {selector})",
                    },
                ],
                "constraints": [
                    {"def": "Distance(A, C)", "value": 3},
                    {"def": "Area(A, B, C)", "value": 6},
                    {"def": "Angle(B, A, C)", "value": "pi/3"},
                    # The selected value must reach the residual boundary.
                    # Merely mentioning P in the answer let a Point-vs-list
                    # selector mismatch pass because exact answer authority is
                    # intentionally delegated to the frozen evaluator.
                    {"def": "Distance(P, C)", "value": "Distance(P, C)"},
                ],
                "guards": [
                    "Bound(t, (0, 1))",
                    "AssumeNe(Area(A, B, C), 0)",
                ],
                "answer": "Distance(P, C)",
                "post_process": "",
            }
        )
    return tuple(fixtures)


def _record_mismatch(
    examples: list[dict[str, Any]],
    config: HarnessConfig,
    **value: Any,
) -> None:
    if len(examples) < config.maximum_mismatch_examples:
        examples.append(value)


def _validate_compiler_manifest(value: Mapping[str, Any]) -> tuple[str, ...]:
    mismatches = []
    if value.get("case_specific_routing") is not False:
        mismatches.append("case_specific_routing")
    if (
        value.get("support_decision_basis")
        != "ast_opcode_type_selector_semantic_abi_only"
    ):
        mismatches.append("support_decision_basis")
    forbidden = value.get("forbidden_support_inputs")
    required_forbidden = {
        "problem_id",
        "corpus_membership",
        "truth",
        "answer_count",
    }
    if not isinstance(forbidden, list) or set(forbidden) != required_forbidden:
        mismatches.append("forbidden_support_inputs")
    if value.get("support_decision_key_fields") != [
        "ast_opcode_set",
        "resolved_operand_result_type_set",
        "selector_kind_set",
        "semantic_abi_version",
    ]:
        mismatches.append("support_decision_key_fields")
    for name in (
        "support_key_includes_problem_id",
        "support_key_includes_source_sha256",
        "support_key_includes_problem_hash",
        "support_key_includes_corpus_shape",
    ):
        if value.get(name) is not False:
            mismatches.append(name)
    return tuple(mismatches)


def _static_support_audit(source: str) -> tuple[str, ...]:
    """Reject forbidden identity/truth inputs in the isolated support decider."""

    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return ("support_decision_source_not_python",)
    forbidden = {
        "case_id",
        "problem_id",
        "source_sha256",
        "problem_sha256",
        "problem_hash",
        "corpus",
        "corpus_membership",
        "corpus_shape",
        "truth",
        "answer_count",
    }
    observed = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            observed.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            observed.add(node.attr.lower())
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            observed.add(node.value.lower())
    return tuple(sorted(forbidden & observed))


def _support_trace_signature(
    value: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], str] | None:
    opcodes = value.get("ast_opcode_set")
    types = value.get("resolved_operand_result_type_set")
    selectors = value.get("selector_kind_set")
    semantic_abi = value.get("semantic_abi_version")
    forbidden_reads = (
        "problem_id_read",
        "corpus_membership_read",
        "truth_read",
        "answer_count_read",
    )
    if (
        not isinstance(opcodes, list)
        or not all(isinstance(item, str) for item in opcodes)
        or not opcodes
        or opcodes != sorted(set(opcodes))
        or not isinstance(types, list)
        or not all(isinstance(item, str) for item in types)
        or not types
        or types != sorted(set(types))
        or not isinstance(selectors, list)
        or not all(isinstance(item, str) for item in selectors)
        or selectors != sorted(set(selectors))
        or not isinstance(semantic_abi, str)
        or not semantic_abi
        or any(value.get(name) is not False for name in forbidden_reads)
    ):
        return None
    expected_key = hashlib.sha256(
        json.dumps(
            {
                "ast_opcode_set": opcodes,
                "resolved_operand_result_type_set": types,
                "selector_kind_set": selectors,
                "semantic_abi_version": semantic_abi,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if value.get("support_key_sha256") != expected_key:
        return None
    return tuple(opcodes), tuple(types), tuple(selectors), semantic_abi


def _synthetic_unseen_problem(
    problem: Mapping[str, Any], problem_sha256: str
) -> dict[str, Any]:
    synthetic = json.loads(
        json.dumps(problem, ensure_ascii=False, allow_nan=False)
    )
    synthetic["id"] = f"kernel-unseen-{problem_sha256[:24]}"
    changed = False
    for constraint in synthetic.get("constraints", ()):
        value = constraint.get("value")
        if isinstance(value, int) and not isinstance(value, bool):
            constraint["value"] = value + 1
            changed = True
            break
        if isinstance(value, float) and math.isfinite(value):
            constraint["value"] = math.nextafter(value, math.inf)
            changed = True
            break
    if not changed:
        expression_slots = [
            *((item, "expr") for item in synthetic.get("construction", ())),
            *((item, "def") for item in synthetic.get("constraints", ())),
        ]

        class PerturbFirstNumber(ast.NodeTransformer):
            changed = False

            def visit_Constant(self, node: ast.Constant) -> ast.AST:
                if self.changed or isinstance(node.value, bool) or not isinstance(
                    node.value, int | float
                ):
                    return node
                self.changed = True
                value = node.value + 1 if isinstance(node.value, int) else math.nextafter(
                    node.value, math.inf
                )
                return ast.copy_location(ast.Constant(value=value), node)

        for container, key in expression_slots:
            source = container.get(key)
            if not isinstance(source, str) or not source:
                continue
            try:
                tree = ast.parse(source, mode="eval")
            except SyntaxError:
                continue
            transformer = PerturbFirstNumber()
            transformed = transformer.visit(tree)
            if transformer.changed:
                container[key] = ast.unparse(ast.fix_missing_locations(transformed))
                break
    return synthetic


def qualify_cases(
    cases: Sequence[tuple[str, Mapping[str, Any], str]],
    adapter: KernelQualificationAdapter,
    config: HarnessConfig | None = None,
    replay_probes: Mapping[str, Sequence[Probe]] | None = None,
) -> dict[str, Any]:
    """Run the complete differential and core-determinism qualification gate."""

    if config is None:
        config = HarnessConfig()
    if tuple(config.cores) != QUALIFICATION_CORES:
        raise ValueError("qualification core matrix must be exactly 1/2/4/8/15")
    manifest = adapter.compiler_manifest()
    capability_factory = getattr(adapter, "qualification_capabilities", None)
    capabilities = dict(capability_factory()) if callable(capability_factory) else {}
    optimizer_capability = (
        capabilities.get("optimizer_replay") is True
        and capabilities.get("candidate_records") is True
    )
    parallel_capability = (
        capabilities.get("actual_parallel_execution") is True
        and tuple(capabilities.get("parallel_core_counts", ())) == QUALIFICATION_CORES
    )
    manifest_mismatches = (
        *_validate_compiler_manifest(manifest),
        *(
            f"static_support_source:{item}"
            for item in _static_support_audit(adapter.support_decision_source())
        ),
    )
    mismatch_examples: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    compared = 0
    fallback_cases = 0
    all_passed = not manifest_mismatches
    reference_gate_passed = True
    numeric_gate_passed = True
    decision_gate_passed = True
    determinism_gate_passed = True
    fallback_contracts_passed = True
    replay_probe_count = 0
    replay_candidate_record_count = 0
    probe_kind_counts: dict[str, int] = {}
    support_trace_gate_passed = True
    synthetic_route_gate_passed = True
    independent_fixture_gate_passed = True
    synthetic_case_count = 0
    support_signature_routes: dict[
        tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], str], bool
    ] = {}
    if manifest_mismatches:
        _record_mismatch(
            mismatch_examples,
            config,
            kind="compiler_manifest",
            fields=list(manifest_mismatches),
        )
    for case_id, problem, problem_sha256 in cases:
        prepared_by_core = {
            core: adapter.prepare(problem, cores=core) for core in config.cores
        }
        baseline = prepared_by_core[1]
        support_signature = _support_trace_signature(
            baseline.support_decision_trace
        )
        if support_signature is None:
            support_trace_gate_passed = False
            all_passed = False
            _record_mismatch(
                mismatch_examples,
                config,
                case_id=case_id,
                kind="support_decision_trace",
            )
        else:
            prior_route = support_signature_routes.setdefault(
                support_signature, baseline.compiled_supported
            )
            if prior_route != baseline.compiled_supported:
                support_trace_gate_passed = False
                all_passed = False
                _record_mismatch(
                    mismatch_examples,
                    config,
                    case_id=case_id,
                    kind="support_route_changed_for_same_primitive_type_set",
                )
        if any(
            prepared.dimension != baseline.dimension
            or tuple(prepared.lower) != tuple(baseline.lower)
            or tuple(prepared.upper) != tuple(baseline.upper)
            or prepared.compiled_supported != baseline.compiled_supported
            or prepared.fallback_reason != baseline.fallback_reason
            for prepared in prepared_by_core.values()
        ):
            _record_mismatch(
                mismatch_examples,
                config,
                case_id=case_id,
                kind="core_prepare_contract",
            )
            all_passed = False
            determinism_gate_passed = False
        fallback = not baseline.compiled_supported
        if fallback:
            fallback_cases += 1
        fallback_contract = not fallback or bool(baseline.fallback_reason)
        if not fallback_contract:
            fallback_contracts_passed = False
            _record_mismatch(
                mismatch_examples,
                config,
                case_id=case_id,
                kind="fallback_without_reason",
            )
        probes = list(generate_probes(
            problem_sha256, baseline.lower, baseline.upper, config
        ))
        prepared_replay = getattr(baseline, "optimizer_replay_probes", None)
        if callable(prepared_replay):
            probes.extend(_replay_probes(prepared_replay(), ordinal_start=len(probes)))
        if replay_probes is not None:
            probes.extend(replay_probes.get(case_id, ()))
            probes.extend(replay_probes.get(problem_sha256, ()))
        replay_for_case = sum(
            probe.kind.startswith("optimizer_replay:") for probe in probes
        )
        replay_probe_count += replay_for_case
        replay_candidate_record_count += sum(
            probe.expected_candidate_record is not None for probe in probes
        )
        for probe in probes:
            category = probe.kind.split(":", 1)[0]
            probe_kind_counts[category] = probe_kind_counts.get(category, 0) + 1
        case_passed = fallback_contract
        reference_digest = hashlib.sha256()
        candidate_digests = {
            core: hashlib.sha256() for core in config.cores
        }
        for probe in probes:
            oracle = Observation.from_value(baseline.reference(probe.point.copy()))
            _update_observation_digest(reference_digest, probe, oracle)
            baseline_candidate: Observation | None = None
            for core in config.cores:
                candidate = Observation.from_value(
                    prepared_by_core[core].candidate(probe.point.copy())
                )
                _update_observation_digest(candidate_digests[core], probe, candidate)
                compared += 1
                differences = compare_observations(
                    oracle,
                    candidate,
                    allow_transcendental_2ulp=(
                        config.report_mode == "experimental_numeric_equivalence"
                    ),
                )
                if differences:
                    case_passed = False
                    reference_gate_passed = False
                    if any(
                        field.startswith("value")
                        or field
                        in {
                            "status",
                            "value_count",
                            "transcendental_indices",
                            "transcendental_branch",
                            "transcendental_branch_coverage",
                            "transcendental_residual_indices",
                            "transcendental_residual_branch",
                            "transcendental_residual_branch_coverage",
                            "residuals",
                        }
                        for field in differences
                    ):
                        numeric_gate_passed = False
                    if any(
                        field
                        in {
                            "residuals",
                            "guards",
                            "guard_violations",
                            "hard_feasibility",
                            "hard_failure_tags",
                            "hard_min_margin",
                            "threshold_decisions",
                            "candidate_record",
                            "exception_type",
                            "exception_stage",
                            "nonfinite_classification",
                        }
                        for field in differences
                    ):
                        decision_gate_passed = False
                    _record_mismatch(
                        mismatch_examples,
                        config,
                        case_id=case_id,
                        probe_kind=probe.kind,
                        probe_ordinal=probe.ordinal,
                        core=core,
                        kind="reference_differential",
                        fields=list(differences),
                    )
                if (
                    probe.expected_candidate_record is not None
                    and _canonical_record(probe.expected_candidate_record)
                    != _canonical_record(candidate.candidate_record)
                ):
                    case_passed = False
                    decision_gate_passed = False
                    _record_mismatch(
                        mismatch_examples,
                        config,
                        case_id=case_id,
                        probe_kind=probe.kind,
                        probe_ordinal=probe.ordinal,
                        core=core,
                        kind="optimizer_candidate_record",
                    )
                if baseline_candidate is None:
                    baseline_candidate = candidate
                else:
                    core_differences = compare_core_observations(
                        baseline_candidate, candidate
                    )
                    if core_differences:
                        case_passed = False
                        determinism_gate_passed = False
                        _record_mismatch(
                            mismatch_examples,
                            config,
                            case_id=case_id,
                            probe_kind=probe.kind,
                            probe_ordinal=probe.ordinal,
                            core=core,
                            kind="core_determinism",
                            fields=list(core_differences),
                        )
        all_passed = all_passed and case_passed
        case_rows.append(
            {
                "case_id": case_id,
                "problem_sha256": problem_sha256,
                "compiled_supported": baseline.compiled_supported,
                "fallback_reason": baseline.fallback_reason,
                "fallback_contract_passed": fallback_contract,
                "probe_count": len(probes),
                "optimizer_replay_probe_count": replay_for_case,
                "reference_observation_sha256": reference_digest.hexdigest(),
                "candidate_observation_sha256_by_core": {
                    str(core): candidate_digests[core].hexdigest()
                    for core in config.cores
                },
                "passed": case_passed,
            }
        )
        synthetic = _synthetic_unseen_problem(problem, problem_sha256)
        synthetic_prepared = adapter.prepare(synthetic, cores=1)
        synthetic_case_count += 1
        synthetic_signature = _support_trace_signature(
            synthetic_prepared.support_decision_trace
        )
        if (
            support_signature is None
            or synthetic_signature != support_signature
            or synthetic_prepared.compiled_supported != baseline.compiled_supported
            or synthetic_prepared.fallback_reason != baseline.fallback_reason
        ):
            synthetic_route_gate_passed = False
            all_passed = False
            _record_mismatch(
                mismatch_examples,
                config,
                case_id=case_id,
                synthetic_problem_id=synthetic["id"],
                kind="synthetic_unseen_route",
            )
    corpus_complete = len(cases) == 145
    fallback_coverage = (
        fallback_contracts_passed
        and (fallback_cases > 0 or not config.require_fallback_path)
    )
    replay_coverage = optimizer_capability and (
        replay_probe_count > 0
        and replay_candidate_record_count > 0
    ) or not config.require_optimizer_replay
    independent_fixture_count = 0
    for fixture in independent_ast_composition_fixtures():
        fixture_payload = json.dumps(
            fixture,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        fixture_sha256 = hashlib.sha256(fixture_payload).hexdigest()
        prepared_by_core = {
            core: adapter.prepare(fixture, cores=core) for core in config.cores
        }
        baseline = prepared_by_core[1]
        independent_fixture_count += 1
        fixture_passed = baseline.compiled_supported
        signature = _support_trace_signature(baseline.support_decision_trace)
        expected_selector = fixture["id"].rsplit("-", 1)[-1]
        if signature is None or expected_selector not in signature[2]:
            fixture_passed = False
        probes = generate_probes(
            fixture_sha256, baseline.lower, baseline.upper, config
        )
        for probe in probes:
            oracle = baseline.reference(probe.point.copy())
            one_core = None
            for core in config.cores:
                candidate = prepared_by_core[core].candidate(probe.point.copy())
                differences = compare_observations(
                    oracle,
                    candidate,
                    allow_transcendental_2ulp=(
                        config.report_mode == "experimental_numeric_equivalence"
                    ),
                )
                if differences:
                    fixture_passed = False
                if one_core is None:
                    one_core = candidate
                elif compare_core_observations(one_core, candidate):
                    fixture_passed = False
        if not fixture_passed:
            independent_fixture_gate_passed = False
            all_passed = False
            _record_mismatch(
                mismatch_examples,
                config,
                case_id=fixture["id"],
                kind="independent_ast_composition",
            )
    gates = {
        "corpus_145_complete": corpus_complete,
        "reference_differential_passed": reference_gate_passed,
        "bitwise_or_transcendental_2ulp_passed": numeric_gate_passed,
        "decision_fields_passed": decision_gate_passed,
        "problem_fallback_coverage_passed": fallback_coverage,
        "optimizer_trace_replay_coverage_passed": replay_coverage,
        "optimizer_replay_capability_passed": (
            optimizer_capability or not config.require_optimizer_replay
        ),
        "core_determinism_1_2_4_8_15_passed": (
            determinism_gate_passed and parallel_capability
        ),
        "parallel_determinism_capability_passed": parallel_capability,
        "compiler_generality_manifest_passed": not manifest_mismatches,
        "support_decision_trace_passed": support_trace_gate_passed,
        "synthetic_unseen_route_passed": synthetic_route_gate_passed,
        "independent_ast_composition_passed": independent_fixture_gate_passed,
    }
    study_passed = all(gates.values())
    production_admissible = config.report_mode == "production_strict"
    return {
        "schema_version": REPORT_SCHEMA,
        "report_mode": config.report_mode,
        "passed": study_passed and production_admissible,
        "study_passed": study_passed,
        "production_admissible": production_admissible,
        "policy": {
            "production_float_rule": "all RefNum outputs are bitwise equal",
            "experimental_transcendental_rule": (
                "same branch and at most 2 ULP; never production-admissible"
            ),
            "decision_fields": [
                "residuals",
                "guards",
                "hard_feasibility",
                "candidate_record",
            ],
            "cores": list(config.cores),
            "qualification_capabilities": capabilities,
            "random_probes_per_problem": config.random_probes_per_problem,
            "boundary_and_degenerate_probes": True,
        },
        "case_count": len(cases),
        "compiled_case_count": len(cases) - fallback_cases,
        "fallback_case_count": fallback_cases,
        "observation_comparisons": compared,
        "probe_kind_counts": dict(sorted(probe_kind_counts.items())),
        "optimizer_replay_probe_count": replay_probe_count,
        "optimizer_replay_candidate_record_count": replay_candidate_record_count,
        "synthetic_unseen_case_count": synthetic_case_count,
        "independent_ast_composition_case_count": independent_fixture_count,
        "compiler_manifest": dict(manifest),
        "gates": gates,
        "cases": case_rows,
        "mismatch_examples": mismatch_examples,
    }


def write_report(report: Mapping[str, Any], destination: Path) -> None:
    payload = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n"
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(destination)


def _load_adapter(specification: str) -> KernelQualificationAdapter:
    module_name, separator, factory_name = specification.partition(":")
    if not separator:
        factory_name = "create_adapter"
    factory: Callable[[], KernelQualificationAdapter] = getattr(
        importlib.import_module(module_name), factory_name
    )
    return factory()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--adapter", required=True, help="module[:factory]")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--replay-trace", type=Path)
    parser.add_argument(
        "--report-mode",
        choices=("production_strict", "experimental_numeric_equivalence"),
        default="production_strict",
    )
    arguments = parser.parse_args()
    report = qualify_cases(
        load_corpus(arguments.corpus),
        _load_adapter(arguments.adapter),
        HarnessConfig(report_mode=arguments.report_mode),
        replay_probes=(
            None
            if arguments.replay_trace is None
            else load_replay_trace(arguments.replay_trace)
        ),
    )
    write_report(report, arguments.report)
    raise SystemExit(0 if report["passed"] else 2)


if __name__ == "__main__":
    main()
