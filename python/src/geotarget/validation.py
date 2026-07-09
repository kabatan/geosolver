"""JSON Schema and graph-wide semantic validation for GeoTarget protocols."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator

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


def _ref_id(value: object) -> str:
    return cast(str, value)


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


def _problem_semantic_issues(document: Mapping[str, object]) -> list[ValidationIssue]:
    plugins = _sequence(document["plugin_locks"])
    variables = _sequence(document["variables"])
    nodes = _sequence(document["graph"])
    issues = _duplicate_issues(plugins, key="plugin_id", path="plugin_locks")
    issues.extend(_duplicate_issues(variables, key="id", path="variables"))
    issues.extend(_duplicate_issues(nodes, key="id", path="graph"))

    known_plugins = {cast(str, cast(Mapping[str, object], item)["plugin_id"]) for item in plugins}
    known_variables = {cast(str, cast(Mapping[str, object], item)["id"]) for item in variables}
    known_nodes = {cast(str, cast(Mapping[str, object], item)["id"]) for item in nodes}
    seen_nodes: set[str] = set()

    def check_ref(raw: object, path: str, *, require_previous: bool = False) -> None:
        node_id = _ref_id(raw)
        if node_id not in known_nodes:
            issues.append(ValidationIssue(path, f"unknown node reference {node_id!r}"))
        elif require_previous and node_id not in seen_nodes:
            issues.append(ValidationIssue(path, f"non-topological node reference {node_id!r}"))

    def check_owner(qualified: str, path: str) -> None:
        owner, _ = qualified_symbol(qualified)
        if owner not in known_plugins:
            issues.append(ValidationIssue(path, f"symbol uses unlocked plugin {owner!r}"))

    for index, raw in enumerate(variables):
        variable_spec = cast(Mapping[str, object], raw)
        check_owner(cast(str, variable_spec["type_id"]), f"variables.{index}.type_id")

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
            kwargs = cast(Mapping[str, object], node["kwargs"])
            for key, ref in kwargs.items():
                check_ref(ref, f"graph.{index}.kwargs.{key}", require_previous=True)
        elif kind == "select":
            check_owner(cast(str, node["selector"]), f"graph.{index}.selector")
            check_ref(node["choice"], f"graph.{index}.choice", require_previous=True)
            for arg_index, ref in enumerate(_sequence(node["args"])):
                check_ref(ref, f"graph.{index}.args.{arg_index}", require_previous=True)
            kwargs = cast(Mapping[str, object], node["kwargs"])
            for key, ref in kwargs.items():
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
        previous = locations.get(node_id)
        if previous is not None:
            issues.append(
                ValidationIssue(
                    path,
                    f"semantic role node {node_id!r} is already used at {previous}",
                )
            )
        else:
            locations[node_id] = path
    return issues


def _plugin_semantic_issues(document: Mapping[str, object]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
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
            symbol = cast(str, cast(Mapping[str, object], raw)["id"])
            symbol_owner, _ = qualified_symbol(symbol)
            if symbol_owner != owner:
                issues.append(
                    ValidationIssue(
                        f"{collection}.{index}.id",
                        f"symbol is owned by {symbol_owner!r}, not manifest plugin {owner!r}",
                    )
                )
    operation_locations: dict[str, str] = {}
    for collection in ("primitives", "relations", "guards", "domains", "branches"):
        for index, raw in enumerate(_sequence(document[collection])):
            symbol = cast(str, cast(Mapping[str, object], raw)["id"])
            previous = operation_locations.get(symbol)
            if previous is not None:
                issues.append(
                    ValidationIssue(
                        f"{collection}.{index}.id",
                        f"operation id is already used at {previous}",
                    )
                )
            else:
                operation_locations[symbol] = f"{collection}.{index}.id"
    return issues


def _result_semantic_issues(document: Mapping[str, object]) -> list[ValidationIssue]:
    exact = _sequence(document["exact_answers"])
    provisional = _sequence(document["provisional_answers"])
    issues: list[ValidationIssue] = []
    if document["search_status"] == "empty_certified" and (exact or provisional):
        issues.append(
            ValidationIssue(
                "search_status",
                "empty_certified results cannot contain exact or provisional answers",
            )
        )
    resume = cast(Mapping[str, object], document["resume_identity"])
    issues.extend(
        _duplicate_issues(
            _sequence(resume["plugin_locks"]),
            key="plugin_id",
            path="resume_identity.plugin_locks",
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
    if version == "geotarget.problem/v1":
        issues = _problem_semantic_issues(mapping)
    elif version == "geotarget.plugin/v1":
        issues = _plugin_semantic_issues(mapping)
    elif version == "geotarget.solve-result/v1":
        issues = _result_semantic_issues(mapping)
    else:
        issues = []
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
