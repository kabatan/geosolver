from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

from geosolver.problem.adapter import PREDICATE_ALIASES


@dataclass(frozen=True)
class RuntimeContract:
    min_args: int
    max_positional: int | None
    parameters: tuple[str, ...]
    allowed_keywords: frozenset[str]
    variadic: bool
    result_kind: str

    def public_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parameters"] = list(self.parameters)
        payload["allowed_keywords"] = sorted(self.allowed_keywords)
        return payload


@lru_cache(maxsize=1)
def catalog_document() -> dict[str, Any]:
    return json.loads(
        files("geosolver.problem").joinpath("catalog.json").read_text(encoding="utf-8")
    )


def _argument_name(node: ast.expr, index: int) -> str:
    return node.id if isinstance(node, ast.Name) else f"arg{index + 1}"


def _base_contract(entry: Mapping[str, Any]) -> dict[str, Any] | None:
    identifier = str(entry["id"])
    try:
        expression = ast.parse(str(entry.get("signature", "")), mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(expression, ast.Call) or not isinstance(expression.func, ast.Name):
        return None
    if expression.func.id != identifier:
        return None
    parameters = [_argument_name(argument, index) for index, argument in enumerate(expression.args)]
    parameters.extend(keyword.arg for keyword in expression.keywords if keyword.arg is not None)
    return {
        "min_args": len(expression.args),
        "max_positional": len(parameters),
        "parameters": parameters,
        "allowed_keywords": parameters,
        "variadic": False,
    }


@lru_cache(maxsize=1)
def runtime_contracts() -> dict[str, RuntimeContract]:
    document = catalog_document()
    configuration = document.get("runtime_contract", {})
    overrides = configuration.get("overrides", {})
    result_groups = configuration.get("result_kinds", {})
    result_kind = {
        str(identifier): str(kind)
        for kind, identifiers in result_groups.items()
        for identifier in identifiers
    }
    entries = [*document.get("tools", ()), *document.get("runtime_functions", ())]
    contracts: dict[str, RuntimeContract] = {}
    for entry in entries:
        identifier = str(entry["id"])
        if entry.get("expands_to") is not None:
            continue
        base = _base_contract(entry) or {}
        override = overrides.get(identifier, {})
        merged = {**base, **override}
        if "min_args" not in merged or "max_positional" not in merged:
            continue
        parameters = tuple(str(value) for value in merged.get("parameters", ()))
        allowed = override.get("allowed_keywords", merged.get("allowed_keywords", parameters))
        contracts[identifier] = RuntimeContract(
            min_args=int(merged["min_args"]),
            max_positional=(
                None if merged["max_positional"] is None else int(merged["max_positional"])
            ),
            parameters=parameters,
            allowed_keywords=frozenset(str(value) for value in allowed),
            variadic=bool(merged.get("variadic", False)),
            result_kind=str(entry.get("result_kind", result_kind.get(identifier, "object"))),
        )
    for public_name, engine_name in PREDICATE_ALIASES.items():
        if engine_name in contracts:
            contracts[public_name] = contracts[engine_name]
    contracts["Degrees"] = RuntimeContract(
        min_args=1,
        max_positional=1,
        parameters=("angle",),
        allowed_keywords=frozenset({"angle"}),
        variadic=False,
        result_kind="scalar",
    )
    return contracts


@lru_cache(maxsize=1)
def selector_values() -> dict[str, tuple[Any, ...]]:
    configured = catalog_document().get("runtime_contract", {}).get("selector_values", {})
    return {str(name): tuple(values) for name, values in configured.items()}


def catalog_payload() -> dict[str, Any]:
    value = deepcopy(catalog_document())
    value.pop("version", None)
    value["schema_version"] = 1
    hidden = {
        "Assume",
        "AssumeEq",
        "AssumeNe",
        "AssumeLt",
        "AssumeLe",
        "AssumeGt",
        "AssumeGe",
        "Bound",
    }
    aliases = {engine: public for public, engine in PREDICATE_ALIASES.items()}
    contracts = runtime_contracts()
    public_tools: list[dict[str, Any]] = []
    for entry in value.get("tools", ()):
        identifier = str(entry["id"])
        if identifier in hidden or identifier.startswith("Assume"):
            continue
        item = dict(entry)
        if identifier in aliases:
            public_name = aliases[identifier]
            item["id"] = public_name
            item["signature"] = str(item.get("signature", "")).replace(identifier, public_name, 1)
            identifier = public_name
        contract = contracts.get(identifier)
        if contract is not None:
            item["runtime_contract"] = contract.public_payload()
        public_tools.append(item)
    value["tools"] = public_tools
    value.setdefault("runtime_functions", []).append(
        {
            "id": "Degrees",
            "category": "measurements",
            "label_ja": "度数変換",
            "signature": "Degrees(angle)",
            "authoring_status": "supported",
            "notes_ja": "radianの角度をdegreeへ変換します。",
            "result_kind": "scalar",
        }
    )
    for entry in value.get("runtime_functions", ()):
        contract = contracts.get(str(entry["id"]))
        if contract is not None:
            entry["runtime_contract"] = contract.public_payload()
    return value
