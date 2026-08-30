"""Public catalog and validator contracts generated from ``dsl-spec.json``."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

from geosolver.problem.dsl_spec import dsl_spec, symbols_by_name


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
def runtime_contracts() -> dict[str, RuntimeContract]:
    return {
        name: RuntimeContract(
            min_args=symbol.min_args,
            max_positional=symbol.max_positional,
            parameters=symbol.parameters,
            allowed_keywords=symbol.allowed_keywords,
            variadic=symbol.variadic,
            result_kind=("scalar" if symbol.output_type in {"scalar", "boolean"} else "object"),
        )
        for name, symbol in symbols_by_name().items()
    }


@lru_cache(maxsize=1)
def selector_values() -> dict[str, tuple[Any, ...]]:
    return dict(dsl_spec().selector_values)


def catalog_document() -> dict[str, Any]:
    """Return the public catalog; retained as the compatibility entrypoint."""
    return catalog_payload()


def catalog_payload() -> dict[str, Any]:
    spec = dsl_spec()
    tools: list[dict[str, Any]] = []
    for symbol in spec.symbols:
        item: dict[str, Any] = {
            "id": symbol.name,
            "aliases": list(symbol.aliases),
            "category": symbol.category,
            "label_ja": symbol.label_ja,
            "signature": symbol.signature,
            "authoring_status": symbol.authoring_status,
            "notes_ja": symbol.notes_ja,
            "semantic_kind": symbol.semantic_kind,
            "positions": sorted(symbol.positions),
            "domain": list(symbol.domain),
            "branches": list(symbol.branches),
            "runtime_contract": symbol.public_contract(),
        }
        if symbol.expands_to is not None:
            item["expands_to"] = symbol.expands_to
        tools.append(item)
    return {
        "schema_version": spec.schema_version,
        "dsl_version": spec.dsl_version,
        "semantics": spec.semantics,
        "categories": spec.categories,
        "tools": tools,
    }
