"""JSON Schema and Base-equivalent semantic validation for GeoTarget protocols."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from math import gcd
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator

from geotarget.canonical import CanonicalJsonError, canonical_bytes, canonical_json
from geotarget.identifiers import qualified_symbol

SCHEMA_FILES: dict[str, str] = {
    "geotarget.problem/v1": "problem-spec-v1.schema.json",
    "geotarget.plugin/v1": "plugin-manifest-v1.schema.json",
    "geotarget.solve-options/v1": "solve-options-v1.schema.json",
    "geotarget.solve-result/v1": "solve-result-v1.schema.json",
}

SCHEMA_ALIASES: dict[str, str] = {
    "problem": "geotarget.problem/v1",
    "plugin-manifest": "geotarget.plugin/v1",
    "solve-options": "geotarget.solve-options/v1",
    "solve-result": "geotarget.solve-result/v1",
}

_CAPABILITY_ORDER = {name: index for index, name in enumerate(("C0", "C1", "C2", "C3V", "C3A"))}
_SAFE_JSON_INTEGER = (1 << 53) - 1
_MAX_SEED = (1 << 64) - 1


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    message: str


class ProtocolValidationError(ValueError):
    """Raised with all deterministic validation issues for a document."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        if not issues:
            raise ValueError("ProtocolValidationError requires at least one issue")
        self.issues = tuple(issues)
        rendered = "; ".join(
            f"{issue.path}: {issue.message}" if issue.path else issue.message
            for issue in self.issues
        )
        super().__init__(rendered)


def _reject_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def parse_json(text: str) -> object:
    """Parse strict JSON while rejecting duplicate keys and NaN/Infinity."""

    return cast(
        object,
        json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant),
    )


def load_json(path: str | Path) -> object:
    return parse_json(Path(path).read_text(encoding="utf-8"))


def schema_directory(explicit: str | Path | None = None) -> Path:
    """Locate the canonical schema directory in source or an explicit deployment."""

    if explicit is not None:
        candidate = Path(explicit).resolve()
        if candidate.is_dir():
            return candidate
        raise FileNotFoundError(f"schema directory does not exist: {candidate}")
    configured = os.environ.get("GEOTARGET_SCHEMA_DIR")
    if configured:
        return schema_directory(configured)
    module_path = Path(__file__).resolve()
    bundled = module_path.parent / "_schemas"
    if all((bundled / filename).is_file() for filename in SCHEMA_FILES.values()):
        return bundled
    for parent in module_path.parents:
        candidate = parent / "schemas"
        if all((candidate / filename).is_file() for filename in SCHEMA_FILES.values()):
            return candidate
    raise FileNotFoundError(
        "GeoTarget schemas were not found; set GEOTARGET_SCHEMA_DIR "
        "to the canonical schema directory"
    )


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProtocolValidationError((ValidationIssue(context, "must be an object"),))
    return cast(Mapping[str, object], value)


def _sequence(value: object) -> Sequence[object]:
    if not isinstance(value, list):
        raise AssertionError("JSON Schema admitted a non-array")
    return cast(Sequence[object], value)


def _schema_version(document: Mapping[str, object], requested: str | None) -> str:
    if requested is not None:
        version = SCHEMA_ALIASES.get(requested, requested)
    else:
        raw = document.get("schema_version")
        if not isinstance(raw, str):
            raise ProtocolValidationError(
                (ValidationIssue("schema_version", "is required and must be a string"),)
            )
        version = raw
    if version not in SCHEMA_FILES:
        raise ProtocolValidationError(
            (ValidationIssue("schema_version", f"unsupported schema version: {version!r}"),)
        )
    return version


def _load_schema(version: str, explicit_directory: str | Path | None) -> Mapping[str, object]:
    path = schema_directory(explicit_directory) / SCHEMA_FILES[version]
    schema = _mapping(load_json(path), context=str(path))
    Draft202012Validator.check_schema(schema)
    return schema


def _schema_issues(
    document: Mapping[str, object], schema: Mapping[str, object]
) -> list[ValidationIssue]:
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    return [
        ValidationIssue(
            ".".join(str(part) for part in error.absolute_path),
            error.message,
        )
        for error in errors
    ]


def _duplicate_issues(values: Sequence[object], *, key: str, path: str) -> list[ValidationIssue]:
    seen: set[str] = set()
    issues: list[ValidationIssue] = []
    for index, raw in enumerate(values):
        item = cast(Mapping[str, object], raw)
        value = cast(str, item[key])
        if value in seen:
            issues.append(ValidationIssue(f"{path}.{index}.{key}", f"duplicate value {value!r}"))
        seen.add(value)
    return issues


def _canonical_lock_issues(values: Sequence[object], *, path: str) -> list[ValidationIssue]:
    issues = _duplicate_issues(values, key="plugin_id", path=path)
    ids = [cast(str, cast(Mapping[str, object], item)["plugin_id"]) for item in values]
    if ids != sorted(ids):
        issues.append(ValidationIssue(path, "plugin locks must be sorted by plugin_id"))
    for index, raw in enumerate(values):
        item = cast(Mapping[str, object], raw)
        if item["version"] == "0.0.0" or item["core_abi"] == "0.0.0":
            issues.append(
                ValidationIssue(f"{path}.{index}", "plugin version and core ABI 0.0.0 are reserved")
            )
    return issues


def _jcs_issues(document: Mapping[str, object]) -> list[ValidationIssue]:
    try:
        canonical_bytes(document)
    except CanonicalJsonError as exc:
        return [ValidationIssue("document", f"not in the RFC 8785 input domain: {exc}")]
    return []


def _finite_decimal(value: object, path: str, issues: list[ValidationIssue]) -> Decimal | None:
    try:
        if isinstance(value, bool):
            raise InvalidOperation
        if isinstance(value, float):
            if not math.isfinite(value):
                raise InvalidOperation
            result = Decimal(repr(value))
        elif isinstance(value, int):
            if abs(value) > _SAFE_JSON_INTEGER:
                raise InvalidOperation
            result = Decimal(value)
        elif isinstance(value, str):
            result = Decimal(value)
            if result.is_zero() and value.startswith("-"):
                issues.append(ValidationIssue(path, "negative zero is not canonical"))
        else:
            raise InvalidOperation
        if not result.is_finite():
            raise InvalidOperation
        return result
    except InvalidOperation:
        issues.append(ValidationIssue(path, "must be a finite canonical decimal"))
        return None


def _problem_semantic_issues(document: Mapping[str, object]) -> list[ValidationIssue]:
    plugins = _sequence(document["plugin_locks"])
    variables = _sequence(document["variables"])
    nodes = _sequence(document["graph"])
    issues = _canonical_lock_issues(plugins, path="plugin_locks")
    issues.extend(_duplicate_issues(variables, key="id", path="variables"))
    issues.extend(_duplicate_issues(nodes, key="id", path="graph"))

    known_plugins = {cast(str, cast(Mapping[str, object], item)["plugin_id"]) for item in plugins}
    known_variables = {cast(str, cast(Mapping[str, object], item)["id"]) for item in variables}
    known_nodes = {cast(str, cast(Mapping[str, object], item)["id"]) for item in nodes}
    seen_nodes: set[str] = set()

    def check_ref(raw: object, path: str, *, require_previous: bool = False) -> None:
        node_id = cast(str, raw)
        if node_id not in known_nodes:
            issues.append(ValidationIssue(path, f"unknown node reference {node_id!r}"))
        elif require_previous and node_id not in seen_nodes:
            issues.append(ValidationIssue(path, f"non-topological node reference {node_id!r}"))

    def check_owner(qualified: str, path: str) -> None:
        owner, _ = qualified_symbol(qualified)
        if owner not in known_plugins:
            issues.append(ValidationIssue(path, f"symbol uses unlocked plugin {owner!r}"))

    for index, raw in enumerate(variables):
        variable = cast(Mapping[str, object], raw)
        prefix = f"variables.{index}"
        check_owner(cast(str, variable["type_id"]), f"{prefix}.type_id")
        origin = _finite_decimal(variable["origin"], f"{prefix}.origin", issues)
        scale = _finite_decimal(variable["scale"], f"{prefix}.scale", issues)
        lower = (
            _finite_decimal(variable["lower"], f"{prefix}.lower", issues)
            if "lower" in variable
            else None
        )
        upper = (
            _finite_decimal(variable["upper"], f"{prefix}.upper", issues)
            if "upper" in variable
            else None
        )
        if scale is not None and scale <= 0:
            issues.append(ValidationIssue(f"{prefix}.scale", "must be strictly positive"))
        if lower is not None and upper is not None and lower >= upper:
            issues.append(ValidationIssue(prefix, "lower bound must be strictly below upper bound"))
        if origin is not None and lower is not None and origin < lower:
            issues.append(ValidationIssue(f"{prefix}.origin", "is below the lower bound"))
        if origin is not None and upper is not None and origin > upper:
            issues.append(ValidationIssue(f"{prefix}.origin", "is above the upper bound"))

    for index, raw in enumerate(nodes):
        node = cast(Mapping[str, object], raw)
        node_id = cast(str, node["id"])
        kind = node["kind"]
        if kind == "literal":
            check_owner(cast(str, node["type_id"]), f"graph.{index}.type_id")
        elif kind == "reference":
            variable_id = cast(str, node["variable"])
            if variable_id not in known_variables:
                issues.append(
                    ValidationIssue(
                        f"graph.{index}.variable", f"unknown variable reference {variable_id!r}"
                    )
                )
        elif kind == "call":
            check_owner(cast(str, node["operation"]), f"graph.{index}.operation")
            for arg_index, ref in enumerate(_sequence(node["args"])):
                check_ref(ref, f"graph.{index}.args.{arg_index}", require_previous=True)
            for key, ref in cast(Mapping[str, object], node["kwargs"]).items():
                check_ref(ref, f"graph.{index}.kwargs.{key}", require_previous=True)
        elif kind == "select":
            check_owner(cast(str, node["selector"]), f"graph.{index}.selector")
            check_ref(node["choice"], f"graph.{index}.choice", require_previous=True)
            for arg_index, ref in enumerate(_sequence(node["args"])):
                check_ref(ref, f"graph.{index}.args.{arg_index}", require_previous=True)
            for key, ref in cast(Mapping[str, object], node["kwargs"]).items():
                check_ref(ref, f"graph.{index}.kwargs.{key}", require_previous=True)
        seen_nodes.add(node_id)

    role_nodes: list[tuple[str, str]] = []
    for collection in ("relations", "guards", "domains"):
        for index, raw in enumerate(_sequence(document[collection])):
            item = cast(Mapping[str, object], raw)
            node_id = cast(str, item["node"])
            path = f"{collection}.{index}.node"
            check_ref(node_id, path)
            role_nodes.append((node_id, path))
    target = cast(str, document["target"])
    check_ref(target, "target")
    role_nodes.append((target, "target"))
    locations: dict[str, str] = {}
    for node_id, path in role_nodes:
        if node_id in locations:
            issues.append(
                ValidationIssue(
                    path,
                    f"semantic role node {node_id!r} is already used at {locations[node_id]}",
                )
            )
        else:
            locations[node_id] = path
    return issues


def _kernel_issues(kernel: Mapping[str, object], path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    capabilities = [cast(str, item) for item in _sequence(kernel["capabilities"])]
    if capabilities != sorted(capabilities, key=_CAPABILITY_ORDER.__getitem__):
        issues.append(
            ValidationIssue(f"{path}.capabilities", "must use canonical capability order")
        )
    derivative_mode = cast(str, kernel["derivative_mode"])
    if derivative_mode != "none" and "C1" not in capabilities:
        issues.append(ValidationIssue(path, "a derivative mode requires capability C1"))
    return issues


def _plugin_semantic_issues(document: Mapping[str, object]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if document["version"] == "0.0.0" or document["core_abi"] == "0.0.0":
        issues.append(ValidationIssue("version", "plugin version and core ABI 0.0.0 are reserved"))
    collections = (
        "types",
        "primitives",
        "relations",
        "guards",
        "domains",
        "branches",
        "selectors",
    )
    for collection in collections:
        issues.extend(_duplicate_issues(_sequence(document[collection]), key="id", path=collection))
    owner = cast(str, document["plugin_id"])
    for collection in collections:
        for index, raw in enumerate(_sequence(document[collection])):
            item = cast(Mapping[str, object], raw)
            symbol = cast(str, item["id"])
            symbol_owner, _ = qualified_symbol(symbol)
            if symbol_owner != owner:
                issues.append(
                    ValidationIssue(
                        f"{collection}.{index}.id",
                        f"symbol is owned by {symbol_owner!r}, not manifest plugin {owner!r}",
                    )
                )
            kernel_name = {
                "primitives": "kernel",
                "relations": "residual_kernel",
                "guards": "margin_kernel",
                "domains": "margin_kernel",
                "branches": "kernel",
                "selectors": "kernel",
            }.get(collection)
            if kernel_name is not None:
                issues.extend(
                    _kernel_issues(
                        cast(Mapping[str, object], item[kernel_name]),
                        f"{collection}.{index}.{kernel_name}",
                    )
                )
    operation_locations: dict[str, str] = {}
    for collection in ("primitives", "relations", "guards", "domains", "branches"):
        for index, raw in enumerate(_sequence(document[collection])):
            symbol = cast(str, cast(Mapping[str, object], raw)["id"])
            if symbol in operation_locations:
                issues.append(
                    ValidationIssue(
                        f"{collection}.{index}.id",
                        f"operation id is already used at {operation_locations[symbol]}",
                    )
                )
            else:
                operation_locations[symbol] = f"{collection}.{index}.id"
    return issues


def _artifact_issues(artifact: Mapping[str, object], path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not cast(str, artifact["media_type"]).strip():
        issues.append(ValidationIssue(f"{path}.media_type", "cannot be blank"))
    encoded = cast(str, artifact["payload_base64"])
    try:
        payload = base64.b64decode(encoded, validate=True)
        if not payload:
            issues.append(ValidationIssue(f"{path}.payload_base64", "payload cannot be empty"))
        if base64.b64encode(payload).decode("ascii") != encoded:
            issues.append(ValidationIssue(f"{path}.payload_base64", "base64 is not canonical"))
        digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
        if artifact["digest"] != digest:
            issues.append(ValidationIssue(f"{path}.digest", "does not match payload bytes"))
    except (binascii.Error, ValueError):
        issues.append(ValidationIssue(f"{path}.payload_base64", "is not strict base64"))
    return issues


def _rational(raw: object, path: str, issues: list[ValidationIssue]) -> Fraction | None:
    value = cast(Mapping[str, object], raw)
    numerator = int(cast(str, value["numerator"]))
    denominator = int(cast(str, value["denominator"]))
    if gcd(abs(numerator), denominator) != 1:
        issues.append(ValidationIssue(path, "rational must be reduced"))
    return Fraction(numerator, denominator)


def _interval(
    raw: object, path: str, issues: list[ValidationIssue]
) -> tuple[Fraction, Fraction] | None:
    interval = cast(Mapping[str, object], raw)
    lower = _rational(interval["lower"], f"{path}.lower", issues)
    upper = _rational(interval["upper"], f"{path}.upper", issues)
    if lower is None or upper is None:
        return None
    if lower >= upper:
        issues.append(ValidationIssue(path, "interval requires lower < upper"))
    return lower, upper


def _trim_polynomial(polynomial: list[Fraction]) -> list[Fraction]:
    while polynomial and polynomial[-1] == 0:
        polynomial.pop()
    return polynomial


def _polynomial_remainder(dividend: list[Fraction], divisor: list[Fraction]) -> list[Fraction]:
    remainder = _trim_polynomial(dividend.copy())
    while remainder and len(remainder) >= len(divisor):
        offset = len(remainder) - len(divisor)
        factor = remainder[-1] / divisor[-1]
        for index, coefficient in enumerate(divisor):
            remainder[index + offset] -= factor * coefficient
        _trim_polynomial(remainder)
    return remainder


def _square_free(coefficients: list[int]) -> bool:
    polynomial = [Fraction(value) for value in coefficients]
    derivative = [Fraction(index * polynomial[index]) for index in range(1, len(polynomial))]
    _trim_polynomial(polynomial)
    _trim_polynomial(derivative)
    while derivative:
        polynomial, derivative = derivative, _polynomial_remainder(polynomial, derivative)
    return len(polynomial) == 1


def _evaluate_polynomial(coefficients: list[int], value: Fraction) -> Fraction:
    result = Fraction(0)
    for coefficient in reversed(coefficients):
        result = result * value + coefficient
    return result


def _identity_issues(identity: Mapping[str, object], path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    coefficients = [int(cast(str, item)) for item in _sequence(identity["coefficients"])]
    if coefficients[-1] <= 0:
        issues.append(
            ValidationIssue(f"{path}.coefficients", "leading coefficient must be positive")
        )
    divisor = 0
    for coefficient in coefficients:
        divisor = gcd(divisor, abs(coefficient))
    if divisor != 1:
        issues.append(ValidationIssue(f"{path}.coefficients", "polynomial must be primitive"))
    if not _square_free(coefficients):
        issues.append(ValidationIssue(f"{path}.coefficients", "polynomial must be square-free"))
    interval = _interval(identity["isolating_interval"], f"{path}.isolating_interval", issues)
    if interval is not None:
        lower, upper = interval
        if _evaluate_polynomial(coefficients, lower) == 0:
            issues.append(ValidationIssue(path, "lower interval endpoint is a polynomial root"))
        if _evaluate_polynomial(coefficients, upper) == 0:
            issues.append(ValidationIssue(path, "upper interval endpoint is a polynomial root"))
    return issues


def _identity_hash(identity: Mapping[str, object]) -> str:
    coefficients = ",".join(cast(str, item) for item in _sequence(identity["coefficients"]))
    interval = cast(Mapping[str, object], identity["isolating_interval"])
    lower = cast(Mapping[str, object], interval["lower"])
    upper = cast(Mapping[str, object], interval["upper"])
    text = "|".join(
        (
            coefficients,
            cast(str, lower["numerator"]),
            cast(str, lower["denominator"]),
            cast(str, upper["numerator"]),
            cast(str, upper["denominator"]),
            str(identity["real_root_index"]),
        )
    )
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"


def _branch_issues(values: Sequence[object], path: str) -> list[ValidationIssue]:
    seen: set[str] = set()
    issues: list[ValidationIssue] = []
    for index, raw in enumerate(values):
        node = cast(str, cast(Mapping[str, object], raw)["choice_node"])
        if node in seen:
            issues.append(ValidationIssue(f"{path}.{index}.choice_node", "duplicate choice node"))
        seen.add(node)
    return issues


def _enclosure(
    raw: object, path: str, issues: list[ValidationIssue]
) -> tuple[Decimal, Decimal] | None:
    value = cast(Mapping[str, object], raw)
    lower = _finite_decimal(value["lower"], f"{path}.lower", issues)
    upper = _finite_decimal(value["upper"], f"{path}.upper", issues)
    if lower is None or upper is None:
        return None
    if lower > upper:
        issues.append(ValidationIssue(path, "enclosure requires lower <= upper"))
    return lower, upper


def _environment_lock_issues(lock: Mapping[str, object], path: str) -> list[ValidationIssue]:
    return _canonical_lock_issues(_sequence(lock["plugin_locks"]), path=f"{path}.plugin_locks")


def _result_semantic_issues(document: Mapping[str, object]) -> list[ValidationIssue]:
    exact = _sequence(document["exact_answers"])
    provisional = _sequence(document["provisional_answers"])
    issues: list[ValidationIssue] = []
    if document["target_image_status"] == "empty_certified" and (exact or provisional):
        issues.append(
            ValidationIssue("target_image_status", "certified-empty result cannot contain answers")
        )

    environment = cast(Mapping[str, object], document["environment_lock"])
    problem_hash = cast(str, environment["problem_hash"])
    issues.extend(_environment_lock_issues(environment, "environment_lock"))
    evidence = cast(Mapping[str, object], document["evidence_log"])
    if not cast(str, evidence["location"]).strip():
        issues.append(ValidationIssue("evidence_log.location", "cannot be blank"))

    identities: set[str] = set()
    for index, raw in enumerate(exact):
        answer = cast(Mapping[str, object], raw)
        prefix = f"exact_answers.{index}"
        identity = cast(Mapping[str, object], answer["identity"])
        issues.extend(_identity_issues(identity, f"{prefix}.identity"))
        identity_key = canonical_json(identity)
        if identity_key in identities:
            issues.append(ValidationIssue(f"{prefix}.identity", "duplicate exact identity"))
        identities.add(identity_key)
        _finite_decimal(answer["approximation"], f"{prefix}.approximation", issues)
        issues.extend(
            _branch_issues(_sequence(answer["branch_signature"]), f"{prefix}.branch_signature")
        )
        configuration = cast(Mapping[str, object], answer["configuration_certificate"])
        target = cast(Mapping[str, object], answer["target_certificate"])
        issues.extend(
            _artifact_issues(
                cast(Mapping[str, object], configuration["artifact"]),
                f"{prefix}.configuration_certificate.artifact",
            )
        )
        issues.extend(
            _artifact_issues(
                cast(Mapping[str, object], target["artifact"]),
                f"{prefix}.target_certificate.artifact",
            )
        )
        if configuration["problem_hash"] != target["problem_hash"]:
            issues.append(ValidationIssue(prefix, "configuration and target problems differ"))
        if configuration["problem_hash"] != problem_hash:
            issues.append(
                ValidationIssue(prefix, "certificate problem differs from environment lock")
            )
        if target["identity_hash"] != _identity_hash(identity):
            issues.append(ValidationIssue(f"{prefix}.target_certificate", "identity hash mismatch"))

    for index, raw in enumerate(provisional):
        answer = cast(Mapping[str, object], raw)
        prefix = f"provisional_answers.{index}"
        _enclosure(answer["target"], f"{prefix}.target", issues)
        residual = _finite_decimal(
            answer["canonical_residual_bound"], f"{prefix}.canonical_residual_bound", issues
        )
        if residual is not None and residual < 0:
            issues.append(
                ValidationIssue(f"{prefix}.canonical_residual_bound", "cannot be negative")
            )
        issues.extend(
            _branch_issues(_sequence(answer["branch_signature"]), f"{prefix}.branch_signature")
        )
        guard_nodes: set[str] = set()
        for guard_index, guard_raw in enumerate(_sequence(answer["guard_enclosures"])):
            guard = cast(Mapping[str, object], guard_raw)
            guard_path = f"{prefix}.guard_enclosures.{guard_index}"
            node = cast(str, guard["node"])
            if node in guard_nodes:
                issues.append(ValidationIssue(f"{guard_path}.node", "duplicate guard node"))
            guard_nodes.add(node)
            enclosure = _enclosure(guard["enclosure"], f"{guard_path}.enclosure", issues)
            if enclosure is not None:
                lower, _ = enclosure
                if guard["strict"] and lower <= 0:
                    issues.append(ValidationIssue(guard_path, "strict guard is not separated"))
                if not guard["strict"] and lower < 0:
                    issues.append(ValidationIssue(guard_path, "nonstrict guard crosses below zero"))
        validation = cast(Mapping[str, object], answer["validation"])
        if validation["problem_hash"] != problem_hash:
            issues.append(ValidationIssue(f"{prefix}.validation", "problem hash mismatch"))
        issues.extend(
            _artifact_issues(
                cast(Mapping[str, object], validation["artifact"]),
                f"{prefix}.validation.artifact",
            )
        )

    coverage = cast(Mapping[str, object], document["coverage"])
    proposed = cast(int, coverage["proposed_tasks"])
    completed = cast(int, coverage["completed_tasks"])
    pending = cast(int, coverage["pending_tasks"])
    if completed > proposed:
        issues.append(ValidationIssue("coverage.completed_tasks", "cannot exceed proposed_tasks"))
    if completed + pending > proposed:
        issues.append(
            ValidationIssue("coverage.pending_tasks", "completed plus pending exceeds proposed")
        )
    return issues


def _options_semantic_issues(document: Mapping[str, object]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    _finite_decimal(document["wall_time_seconds"], "wall_time_seconds", issues)
    seed = document["seed"]
    if isinstance(seed, str) and int(seed) > _MAX_SEED:
        issues.append(ValidationIssue("seed", "decimal seed exceeds UInt64"))
    checkpoint = document.get("checkpoint")
    if checkpoint is not None:
        value = cast(Mapping[str, object], checkpoint)
        if not cast(str, value["path"]).strip():
            issues.append(ValidationIssue("checkpoint.path", "cannot be blank"))
        issues.extend(
            _environment_lock_issues(
                cast(Mapping[str, object], value["environment_lock"]),
                "checkpoint.environment_lock",
            )
        )
    return issues


def validate_document(
    document: object,
    *,
    schema: str | None = None,
    schemas: str | Path | None = None,
) -> str:
    """Validate a protocol document and return its canonical schema version."""

    mapping = _mapping(document, context="document")
    version = _schema_version(mapping, schema)
    loaded_schema = _load_schema(version, schemas)
    issues = _schema_issues(mapping, loaded_schema)
    if issues:
        raise ProtocolValidationError(issues)
    issues = _jcs_issues(mapping)
    if version == "geotarget.problem/v1":
        issues.extend(_problem_semantic_issues(mapping))
    elif version == "geotarget.plugin/v1":
        issues.extend(_plugin_semantic_issues(mapping))
    elif version == "geotarget.solve-result/v1":
        issues.extend(_result_semantic_issues(mapping))
    elif version == "geotarget.solve-options/v1":
        issues.extend(_options_semantic_issues(mapping))
    if issues:
        raise ProtocolValidationError(issues)
    return version


def load_and_validate(
    path: str | Path,
    *,
    schema: str | None = None,
    schemas: str | Path | None = None,
) -> tuple[object, str]:
    document = load_json(path)
    return document, validate_document(document, schema=schema, schemas=schemas)
